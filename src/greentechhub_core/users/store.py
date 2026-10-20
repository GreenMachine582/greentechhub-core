"""users.store — the UserStore protocol and InMemoryUserStore.

A UserStore keeps accounts and their linked identities, and nothing more:
resolving a sign-in to an account and checking a password are plain
functions over any store (users.resolve), so every implementation shares one
copy of those rules.

A UserStore here (InMemoryUserStore) and in greentechhub_core.sqlalchemy
(SQLAlchemyUserStore).
"""

import threading
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, Protocol

from greentechhub_core.security.throttle import aware
from greentechhub_core.users.model import (
    LinkedIdentity,
    LinkExists,
    UserAccount,
    UserExists,
    apply_changes,
    new_account,
    normalize_email,
    normalize_username,
)

Clock = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class UserStore(Protocol):
    """Structural contract for a user-account store. Each operation comes as
    an async method plus a `_sync` twin.

    Semantics every implementation keeps (UserStoreContract asserts them):
      - `create(username, link=None, **fields)` adds a new_account(...) and
        returns it; raises ValueError as new_account does, and UserExists
        when the username or email is taken (compared lowercased). With
        `link=(provider, external_subject)` the account and that link are
        added together, or neither: LinkExists when the pair is taken.
      - `get(user_id)`, `by_username(username)` and `by_email(email)` return
        the account or None; the lookups are case-insensitive.
      - `list_users()` returns every account, active or not, by username.
      - `update(user_id, changes)` applies apply_changes(...) and returns the
        updated account, or None for an unknown id; raises as apply_changes
        does, and UserExists for a taken username or email.
      - `link(user_id, provider, external_subject)` ties a sign-in to an
        account and returns the link; raises LinkExists when that pair is
        already linked (to anyone), and KeyError for an unknown user_id.
      - `find_link(provider, external_subject)` returns the link or None.
      - `links_for(user_id)` returns that account's links, oldest first.
      - `touch_link(provider, external_subject)` sets last_seen_at to now.
      - `unlink(provider, external_subject)` deletes the link; returns whether it did.
    Datetimes come back UTC-aware. Accounts are never deleted here: a
    service deactivates them (`update(id, {"active": False})`), so its own
    rows that reference the id stay intact.
    """

    async def create(
        self, username: str, *, link: tuple[str, str] | None = None, **fields: Any
    ) -> UserAccount: ...

    def create_sync(
        self, username: str, *, link: tuple[str, str] | None = None, **fields: Any
    ) -> UserAccount: ...

    async def get(self, user_id: str) -> UserAccount | None: ...

    def get_sync(self, user_id: str) -> UserAccount | None: ...

    async def by_username(self, username: str) -> UserAccount | None: ...

    def by_username_sync(self, username: str) -> UserAccount | None: ...

    async def by_email(self, email: str) -> UserAccount | None: ...

    def by_email_sync(self, email: str) -> UserAccount | None: ...

    async def list_users(self) -> list[UserAccount]: ...

    def list_users_sync(self) -> list[UserAccount]: ...

    async def update(self, user_id: str, changes: Mapping[str, Any]) -> UserAccount | None: ...

    def update_sync(self, user_id: str, changes: Mapping[str, Any]) -> UserAccount | None: ...

    async def link(self, user_id: str, provider: str, external_subject: str) -> LinkedIdentity: ...

    def link_sync(self, user_id: str, provider: str, external_subject: str) -> LinkedIdentity: ...

    async def find_link(self, provider: str, external_subject: str) -> LinkedIdentity | None: ...

    def find_link_sync(self, provider: str, external_subject: str) -> LinkedIdentity | None: ...

    async def links_for(self, user_id: str) -> list[LinkedIdentity]: ...

    def links_for_sync(self, user_id: str) -> list[LinkedIdentity]: ...

    async def touch_link(self, provider: str, external_subject: str) -> None: ...

    def touch_link_sync(self, provider: str, external_subject: str) -> None: ...

    async def unlink(self, provider: str, external_subject: str) -> bool: ...

    def unlink_sync(self, provider: str, external_subject: str) -> bool: ...

    def now(self) -> datetime:
        """The store's clock — what resolve_account compares touch intervals against."""
        ...


def _safe_email(email: str) -> str | None:
    try:
        return normalize_email(email)
    except ValueError:
        return None


def _safe_username(username: str) -> str | None:
    try:
        return normalize_username(username)
    except ValueError:
        return None


class InMemoryUserStore:
    """A process-local UserStore — dicts behind a lock. Nothing persists
    across restarts. The async methods delegate to the sync ones.

    Args:
        clock: returns the current time; tests pass a fake one.
    """

    def __init__(self, *, clock: Clock = _utcnow) -> None:
        self._clock = clock
        self._lock = threading.RLock()
        self._users: dict[str, UserAccount] = {}
        self._links: dict[tuple[str, str], LinkedIdentity] = {}

    def now(self) -> datetime:
        return aware(self._clock())

    def _check_unique(self, account: UserAccount) -> None:
        for other in self._users.values():
            if other.id == account.id:
                continue
            if other.username == account.username:
                raise UserExists("username", account.username)
            if account.email is not None and other.email == account.email:
                raise UserExists("email", account.email)

    def create_sync(
        self, username: str, *, link: tuple[str, str] | None = None, **fields: Any
    ) -> UserAccount:
        account = new_account(username, now=self.now(), **fields)
        with self._lock:
            self._check_unique(account)
            if link is not None and link in self._links:
                raise LinkExists(f"{link[0]}:{link[1]} is already linked")
            self._users[account.id] = account
            if link is not None:
                self.link_sync(account.id, *link)
        return account

    def get_sync(self, user_id: str) -> UserAccount | None:
        with self._lock:
            return self._users.get(user_id)

    def by_username_sync(self, username: str) -> UserAccount | None:
        value = _safe_username(username)
        with self._lock:
            return next((u for u in self._users.values() if u.username == value), None)

    def by_email_sync(self, email: str) -> UserAccount | None:
        value = _safe_email(email)
        if value is None:
            return None
        with self._lock:
            return next((u for u in self._users.values() if u.email == value), None)

    def list_users_sync(self) -> list[UserAccount]:
        with self._lock:
            return sorted(self._users.values(), key=lambda u: u.username)

    def update_sync(self, user_id: str, changes: Mapping[str, Any]) -> UserAccount | None:
        with self._lock:
            account = self._users.get(user_id)
            if account is None:
                return None
            updated = apply_changes(account, changes, now=self.now())
            self._check_unique(updated)
            self._users[user_id] = updated
            return updated

    def link_sync(self, user_id: str, provider: str, external_subject: str) -> LinkedIdentity:
        with self._lock:
            if user_id not in self._users:
                raise KeyError(user_id)
            key = (provider, external_subject)
            if key in self._links:
                raise LinkExists(f"{provider}:{external_subject} is already linked")
            link = LinkedIdentity(provider=provider, external_subject=external_subject,
                                  user_id=user_id, created_at=self.now())
            self._links[key] = link
            return link

    def find_link_sync(self, provider: str, external_subject: str) -> LinkedIdentity | None:
        with self._lock:
            return self._links.get((provider, external_subject))

    def links_for_sync(self, user_id: str) -> list[LinkedIdentity]:
        with self._lock:
            return sorted((link for link in self._links.values() if link.user_id == user_id),
                          key=lambda link: (link.created_at, link.provider))

    def touch_link_sync(self, provider: str, external_subject: str) -> None:
        with self._lock:
            key = (provider, external_subject)
            if key in self._links:
                self._links[key] = replace(self._links[key], last_seen_at=self.now())

    def unlink_sync(self, provider: str, external_subject: str) -> bool:
        with self._lock:
            return self._links.pop((provider, external_subject), None) is not None

    async def create(
        self, username: str, *, link: tuple[str, str] | None = None, **fields: Any
    ) -> UserAccount:
        return self.create_sync(username, link=link, **fields)

    async def get(self, user_id: str) -> UserAccount | None:
        return self.get_sync(user_id)

    async def by_username(self, username: str) -> UserAccount | None:
        return self.by_username_sync(username)

    async def by_email(self, email: str) -> UserAccount | None:
        return self.by_email_sync(email)

    async def list_users(self) -> list[UserAccount]:
        return self.list_users_sync()

    async def update(self, user_id: str, changes: Mapping[str, Any]) -> UserAccount | None:
        return self.update_sync(user_id, changes)

    async def link(self, user_id: str, provider: str, external_subject: str) -> LinkedIdentity:
        return self.link_sync(user_id, provider, external_subject)

    async def find_link(self, provider: str, external_subject: str) -> LinkedIdentity | None:
        return self.find_link_sync(provider, external_subject)

    async def links_for(self, user_id: str) -> list[LinkedIdentity]:
        return self.links_for_sync(user_id)

    async def touch_link(self, provider: str, external_subject: str) -> None:
        self.touch_link_sync(provider, external_subject)

    async def unlink(self, provider: str, external_subject: str) -> bool:
        return self.unlink_sync(provider, external_subject)
