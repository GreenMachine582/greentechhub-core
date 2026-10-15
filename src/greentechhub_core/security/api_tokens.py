"""api_tokens — personal API tokens for scripts and other non-browser
clients — see docs/modules.md#api-tokens.

A token is `generate_token()`'s 256 random bits, handed out once by
`create` and never stored: the store keeps only its SHA-256 (token_hash,
as for single-use tokens), so a leaked table can't be turned back into
working credentials. Unlike a login JWT, a token can be revoked, and
`verify` records when it was last used so its owner can spot a stale or
leaked one.

Each token has an owner (an Identity.subject), a name the owner chose
("backup script"), scopes and an optional expiry. Scopes are permission
strings stored as given: capping them by what the owner is granted, at
creation and on each use, is the adapter's job.

An ApiTokenStore here (InMemoryApiTokenStore) and in
greentechhub_core.sqlalchemy (SQLAlchemyApiTokenStore).
"""

import threading
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from greentechhub_core.security.one_time import token_hash
from greentechhub_core.security.throttle import aware
from greentechhub_core.security.tokens import generate_token

Clock = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class ApiToken:
    """One personal API token, as stored.

    Fields:
        id: 32 hex characters — what list and revoke refer to.
        owner: whose it is (an Identity.subject).
        name: the owner's label for it.
        scopes: the permission strings it carries.
        token_hash: token_hash(token) — the token itself is never stored.
        created_at: UTC.
        expires_at: UTC, or None for a token that doesn't expire.
        last_used_at: when verify last accepted it (UTC), or None.
    """

    id: str
    owner: str
    name: str
    scopes: frozenset[str]
    token_hash: str
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None

    def active(self, now: datetime) -> bool:
        """Not expired at `now`."""
        return self.expires_at is None or aware(self.expires_at) > aware(now)


def new_api_token(
    owner: str,
    name: str,
    scopes: Iterable[str],
    *,
    now: datetime,
    expires_at: datetime | None = None,
) -> tuple[ApiToken, str]:
    """A new ApiToken and its plaintext, checked — what a store's `create`
    adds. Raises ValueError for an empty owner or name, or an `expires_at`
    that isn't after `now`."""
    if not owner or not name:
        raise ValueError("an API token needs an owner and a name")
    now = aware(now)
    if expires_at is not None:
        expires_at = aware(expires_at)
        if expires_at <= now:
            raise ValueError("expires_at must be in the future")
    plaintext = generate_token()
    token = ApiToken(id=uuid.uuid4().hex, owner=owner, name=name, scopes=frozenset(scopes),
                     token_hash=token_hash(plaintext), created_at=now, expires_at=expires_at)
    return token, plaintext


class ApiTokenStore(Protocol):
    """Structural contract for a personal API token store. Each operation
    comes as an async method plus a `_sync` twin.

    Semantics every implementation keeps (ApiTokenStoreContract asserts them):
      - `create(owner, name, scopes, expires_at=None)` returns the new token
        and its plaintext — the only time the plaintext is available. It
        raises ValueError as new_api_token does.
      - `verify(plaintext)` returns the token with last_used_at set to now,
        or None when it's unknown, revoked or expired.
      - `list_for(owner)` returns that owner's tokens, expired ones too,
        newest first.
      - `revoke(token_id, owner=None)` deletes the token and returns whether
        it did. With `owner`, only that owner's token is deleted, so a
        "revoke my token" view needs no separate ownership check.
    Datetimes come back UTC-aware.
    """

    async def create(
        self, owner: str, name: str, scopes: Iterable[str], expires_at: datetime | None = None
    ) -> tuple[ApiToken, str]: ...

    def create_sync(
        self, owner: str, name: str, scopes: Iterable[str], expires_at: datetime | None = None
    ) -> tuple[ApiToken, str]: ...

    async def verify(self, plaintext: str) -> ApiToken | None: ...

    def verify_sync(self, plaintext: str) -> ApiToken | None: ...

    async def list_for(self, owner: str) -> list[ApiToken]: ...

    def list_for_sync(self, owner: str) -> list[ApiToken]: ...

    async def revoke(self, token_id: str, owner: str | None = None) -> bool: ...

    def revoke_sync(self, token_id: str, owner: str | None = None) -> bool: ...


def newest_first(tokens: Iterable[ApiToken]) -> list[ApiToken]:
    """`tokens` by created_at, newest first (id breaks ties, for a stable order)."""
    return sorted(tokens, key=lambda t: (aware(t.created_at), t.id), reverse=True)


class InMemoryApiTokenStore:
    """A process-local ApiTokenStore — a dict of id → ApiToken behind a
    lock. Nothing persists across restarts. The async methods delegate to
    the sync ones.

    Args:
        clock: returns the current time; tests pass a fake one.
    """

    def __init__(self, *, clock: Clock = _utcnow) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._tokens: dict[str, ApiToken] = {}

    def create_sync(
        self, owner: str, name: str, scopes: Iterable[str], expires_at: datetime | None = None
    ) -> tuple[ApiToken, str]:
        token, plaintext = new_api_token(owner, name, scopes, now=self._clock(),
                                         expires_at=expires_at)
        with self._lock:
            self._tokens[token.id] = token
        return token, plaintext

    def verify_sync(self, plaintext: str) -> ApiToken | None:
        digest = token_hash(plaintext)
        now = aware(self._clock())
        with self._lock:
            token = next((t for t in self._tokens.values() if t.token_hash == digest), None)
            if token is None or not token.active(now):
                return None
            token = self._tokens[token.id] = replace(token, last_used_at=now)
            return token

    def list_for_sync(self, owner: str) -> list[ApiToken]:
        with self._lock:
            return newest_first(t for t in self._tokens.values() if t.owner == owner)

    def revoke_sync(self, token_id: str, owner: str | None = None) -> bool:
        with self._lock:
            token = self._tokens.get(token_id)
            if token is None or (owner is not None and token.owner != owner):
                return False
            del self._tokens[token_id]
            return True

    async def create(
        self, owner: str, name: str, scopes: Iterable[str], expires_at: datetime | None = None
    ) -> tuple[ApiToken, str]:
        return self.create_sync(owner, name, scopes, expires_at)

    async def verify(self, plaintext: str) -> ApiToken | None:
        return self.verify_sync(plaintext)

    async def list_for(self, owner: str) -> list[ApiToken]:
        return self.list_for_sync(owner)

    async def revoke(self, token_id: str, owner: str | None = None) -> bool:
        return self.revoke_sync(token_id, owner)
