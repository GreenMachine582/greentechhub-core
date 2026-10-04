"""one_time — expiring, single-use tokens for links such as password reset
and email verification — see docs/modules.md#single-use-tokens.

A token is `generate_token()`'s 256 random bits, handed out once and never
stored: the store keeps only its SHA-256 (an unsalted fast hash is enough
for a value that random), so a leaked table can't be turned back into
working links. Each token has a `purpose`, so a password-reset link can't
verify an email, and a subject (an Identity.subject). Issuing a new token
revokes the subject's earlier unused ones for the same purpose.

Two layers, like login throttling: a TokenStore (InMemoryTokenStore here,
SQLAlchemyTokenStore in greentechhub_core.sqlalchemy) and OneTimeTokens,
the policy over it.
"""

import hashlib
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol

from greentechhub_core.security.throttle import aware
from greentechhub_core.security.tokens import generate_token


def token_hash(token: str) -> str:
    """The SHA-256 hex digest a store keeps in place of `token`."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class TokenRecord:
    """One issued token, as stored.

    Fields:
        token_hash: token_hash(token) — the token itself is never stored.
        purpose: what it's for, e.g. "password_reset".
        subject: who it's for (an Identity.subject).
        created_at, expires_at: UTC.
        used_at: when it was redeemed (UTC), or None while unused.
    """

    token_hash: str
    purpose: str
    subject: str
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None = None

    def valid(self, purpose: str, now: datetime) -> bool:
        """Unused, unexpired and for `purpose`."""
        unexpired = aware(self.expires_at) > aware(now)
        return self.purpose == purpose and self.used_at is None and unexpired


def is_stale(record: TokenRecord, before: datetime) -> bool:
    """Whether `record` can be pruned: it expired, or was used, before `before`."""
    before = aware(before)
    used = record.used_at is not None and aware(record.used_at) < before
    return used or aware(record.expires_at) < before


class TokenStore(Protocol):
    """Structural contract for a single-use token store. Each operation comes
    as an async method plus a `_sync` twin.

    Semantics every implementation keeps (TokenStoreContract asserts them):
      - `get` of an unknown hash is None.
      - `use(hash, at)` sets used_at only if the token is still unused, and
        returns whether it did — atomically, so two redeems at once can't
        both succeed. An unknown hash is False.
      - `revoke(subject, purpose)` deletes that subject's unused tokens for
        that purpose and returns how many.
      - `prune(before)` deletes every record `is_stale` says can go and
        returns how many.
    Datetimes come back UTC-aware.
    """

    async def add(self, record: TokenRecord) -> None: ...

    def add_sync(self, record: TokenRecord) -> None: ...

    async def get(self, token_hash: str) -> TokenRecord | None: ...

    def get_sync(self, token_hash: str) -> TokenRecord | None: ...

    async def use(self, token_hash: str, at: datetime) -> bool: ...

    def use_sync(self, token_hash: str, at: datetime) -> bool: ...

    async def revoke(self, subject: str, purpose: str) -> int: ...

    def revoke_sync(self, subject: str, purpose: str) -> int: ...

    async def prune(self, before: datetime) -> int: ...

    def prune_sync(self, before: datetime) -> int: ...


class InMemoryTokenStore:
    """A process-local TokenStore — a dict of hash → TokenRecord behind a
    lock. Nothing persists across restarts. The async methods delegate to
    the sync ones."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, TokenRecord] = {}

    def add_sync(self, record: TokenRecord) -> None:
        record = replace(
            record,
            created_at=aware(record.created_at),
            expires_at=aware(record.expires_at),
            used_at=aware(record.used_at) if record.used_at is not None else None,
        )
        with self._lock:
            self._records[record.token_hash] = record

    def get_sync(self, token_hash: str) -> TokenRecord | None:
        with self._lock:
            return self._records.get(token_hash)

    def use_sync(self, token_hash: str, at: datetime) -> bool:
        with self._lock:
            record = self._records.get(token_hash)
            if record is None or record.used_at is not None:
                return False
            self._records[token_hash] = replace(record, used_at=aware(at))
            return True

    def revoke_sync(self, subject: str, purpose: str) -> int:
        with self._lock:
            doomed = [
                h for h, r in self._records.items()
                if r.subject == subject and r.purpose == purpose and r.used_at is None
            ]
            for h in doomed:
                del self._records[h]
            return len(doomed)

    def prune_sync(self, before: datetime) -> int:
        with self._lock:
            stale = [h for h, r in self._records.items() if is_stale(r, before)]
            for h in stale:
                del self._records[h]
            return len(stale)

    async def add(self, record: TokenRecord) -> None:
        self.add_sync(record)

    async def get(self, token_hash: str) -> TokenRecord | None:
        return self.get_sync(token_hash)

    async def use(self, token_hash: str, at: datetime) -> bool:
        return self.use_sync(token_hash, at)

    async def revoke(self, subject: str, purpose: str) -> int:
        return self.revoke_sync(subject, purpose)

    async def prune(self, before: datetime) -> int:
        return self.prune_sync(before)


PRUNE_AFTER = timedelta(days=1)
"""How long an expired or used token is kept before prune() drops it."""


class OneTimeTokens:
    """Issue and redeem single-use tokens over a TokenStore. Each method comes
    as an async method plus a `_sync` twin.

    Args:
        store: where the hashes live.
        lifetime: how long a token stays valid (default 1 hour); issue() can
            override it per token (an email verification might get 2 days).
        clock: returns the current time; tests pass a fake one.
    """

    def __init__(
        self,
        store: TokenStore,
        *,
        lifetime: timedelta = timedelta(hours=1),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        _check_lifetime(lifetime)
        self._store = store
        self.lifetime = lifetime
        self._clock = clock

    def _now(self) -> datetime:
        return aware(self._clock())

    def _record(self, token: str, subject: str, purpose: str, lifetime: timedelta | None):
        if not subject or not purpose:
            raise ValueError("a token needs a subject and a purpose")
        lifetime = self.lifetime if lifetime is None else lifetime
        _check_lifetime(lifetime)
        now = self._now()
        return TokenRecord(token_hash=token_hash(token), purpose=purpose, subject=subject,
                           created_at=now, expires_at=now + lifetime)

    # sync

    def issue_sync(self, subject: str, purpose: str, *, lifetime: timedelta | None = None) -> str:
        """A new token for `subject` and `purpose` — the plaintext, returned
        this once; put it in the link. Earlier unused tokens for the same
        subject and purpose stop working."""
        token = generate_token()
        record = self._record(token, subject, purpose, lifetime)
        self._store.revoke_sync(subject, purpose)
        self._store.add_sync(record)
        return token

    def peek_sync(self, token: str, purpose: str) -> str | None:
        """The token's subject if it's valid now, without using it up — e.g.
        to show the "choose a new password" form. None otherwise."""
        record = self._store.get_sync(token_hash(token))
        return record.subject if record is not None and record.valid(purpose, self._now()) else None

    def redeem_sync(self, token: str, purpose: str) -> str | None:
        """Use the token up and return its subject — or None if it's unknown,
        for another purpose (left unused), expired, or already used, including
        by a redeem that got there first."""
        now = self._now()
        record = self._store.get_sync(token_hash(token))
        if record is None or not record.valid(purpose, now):
            return None
        return record.subject if self._store.use_sync(record.token_hash, now) else None

    def prune_sync(self) -> int:
        """Delete tokens that expired or were used over PRUNE_AFTER ago."""
        return self._store.prune_sync(self._now() - PRUNE_AFTER)

    # async

    async def issue(self, subject: str, purpose: str, *, lifetime: timedelta | None = None) -> str:
        token = generate_token()
        record = self._record(token, subject, purpose, lifetime)
        await self._store.revoke(subject, purpose)
        await self._store.add(record)
        return token

    async def peek(self, token: str, purpose: str) -> str | None:
        record = await self._store.get(token_hash(token))
        return record.subject if record is not None and record.valid(purpose, self._now()) else None

    async def redeem(self, token: str, purpose: str) -> str | None:
        now = self._now()
        record = await self._store.get(token_hash(token))
        if record is None or not record.valid(purpose, now):
            return None
        return record.subject if await self._store.use(record.token_hash, now) else None

    async def prune(self) -> int:
        return await self._store.prune(self._now() - PRUNE_AFTER)


def _check_lifetime(lifetime: timedelta) -> None:
    if lifetime <= timedelta(0):
        raise ValueError("lifetime must be positive")
