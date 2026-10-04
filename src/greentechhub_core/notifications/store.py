"""notifications.store — NotificationStore (where notifications live) and
InMemoryNotificationStore, its reference implementation; the database-backed
one is greentechhub_core.sqlalchemy's SQLAlchemyNotificationStore.

Every read and write is scoped to one recipient, so a caller can only ever
mark its own user's notifications read: an id belonging to someone else is
ignored, not an error.
"""

import threading
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime
from typing import Protocol

from greentechhub_core.notifications.model import Notification, aware


class NotificationStore(Protocol):
    """Structural contract for a notification store. Each operation comes as
    an async method plus a `_sync` twin, like GrantStore.

    Semantics every implementation keeps (NotificationStoreContract asserts
    them):
      - `list_for` returns a recipient's notifications newest first (by
        created_at, then id), at most `limit`, only unread ones with
        `unread_only`; an unknown recipient gives [].
      - `mark_read` marks only `recipient`'s own unread notifications among
        `ids`, and `mark_all_read` all of them; both return how many changed.
      - `prune(before)` deletes read notifications created before `before`
        and returns how many; unread ones are never pruned.
    Datetimes come back UTC-aware.
    """

    async def add(self, notification: Notification) -> None: ...

    def add_sync(self, notification: Notification) -> None: ...

    async def list_for(
        self, recipient: str, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]: ...

    def list_for_sync(
        self, recipient: str, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]: ...

    async def unread_count(self, recipient: str) -> int: ...

    def unread_count_sync(self, recipient: str) -> int: ...

    async def mark_read(self, recipient: str, ids: Iterable[str], *, at: datetime) -> int: ...

    def mark_read_sync(self, recipient: str, ids: Iterable[str], *, at: datetime) -> int: ...

    async def mark_all_read(self, recipient: str, *, at: datetime) -> int: ...

    def mark_all_read_sync(self, recipient: str, *, at: datetime) -> int: ...

    async def prune(self, before: datetime) -> int: ...

    def prune_sync(self, before: datetime) -> int: ...


def newest_first(notifications: Iterable[Notification]) -> list[Notification]:
    """`notifications` sorted the way list_for returns them."""
    return sorted(notifications, key=lambda n: (aware(n.created_at), n.id), reverse=True)


class InMemoryNotificationStore:
    """A process-local NotificationStore — a dict of id → Notification behind
    a lock. Nothing persists across restarts. The async methods delegate to
    the sync ones."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, Notification] = {}

    def add_sync(self, notification: Notification) -> None:
        with self._lock:
            self._items[notification.id] = notification

    def list_for_sync(
        self, recipient: str, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]:
        with self._lock:
            mine = [
                n for n in self._items.values()
                if n.recipient == recipient and not (unread_only and n.read)
            ]
        return newest_first(mine)[:limit]

    def unread_count_sync(self, recipient: str) -> int:
        with self._lock:
            return sum(1 for n in self._items.values() if n.recipient == recipient and not n.read)

    def _mark(self, recipient: str, ids: set[str] | None, at: datetime) -> int:
        with self._lock:
            changed = 0
            for key, n in self._items.items():
                if n.recipient == recipient and not n.read and (ids is None or key in ids):
                    self._items[key] = replace(n, read_at=aware(at))
                    changed += 1
            return changed

    def mark_read_sync(self, recipient: str, ids: Iterable[str], *, at: datetime) -> int:
        return self._mark(recipient, set(ids), at)

    def mark_all_read_sync(self, recipient: str, *, at: datetime) -> int:
        return self._mark(recipient, None, at)

    def prune_sync(self, before: datetime) -> int:
        before = aware(before)
        with self._lock:
            stale = [k for k, n in self._items.items() if n.read and aware(n.created_at) < before]
            for key in stale:
                del self._items[key]
            return len(stale)

    async def add(self, notification: Notification) -> None:
        self.add_sync(notification)

    async def list_for(
        self, recipient: str, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]:
        return self.list_for_sync(recipient, unread_only=unread_only, limit=limit)

    async def unread_count(self, recipient: str) -> int:
        return self.unread_count_sync(recipient)

    async def mark_read(self, recipient: str, ids: Iterable[str], *, at: datetime) -> int:
        return self.mark_read_sync(recipient, ids, at=at)

    async def mark_all_read(self, recipient: str, *, at: datetime) -> int:
        return self.mark_all_read_sync(recipient, at=at)

    async def prune(self, before: datetime) -> int:
        return self.prune_sync(before)
