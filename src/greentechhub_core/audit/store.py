"""audit.store — AuditStore (where entries live) and InMemoryAuditStore,
its reference implementation; the database-backed one is
greentechhub_core.sqlalchemy's SQLAlchemyAuditStore.
"""

import threading
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime
from typing import Protocol

from greentechhub_core.audit.model import AuditEntry
from greentechhub_core.security.throttle import aware

Target = tuple[str, str | None]
"""An entries() target filter: (type, id), or (type, None) for every record of that type."""


class AuditStore(Protocol):
    """Structural contract for an audit log. Each operation comes as an
    async method plus a `_sync` twin.

    Semantics every implementation keeps (AuditStoreContract asserts them):
      - `entries` returns them newest first (by `at`, then id), at most
        `limit`, filtered by every argument given: `actor`; `action` exactly,
        or as a prefix when it ends in "." ("stock." → every stock action);
        `target` (type, id) or (type, None); and `before` (strictly older),
        the cursor for paging back.
      - `prune(before)` deletes entries older than `before` and returns how many.
    Datetimes come back UTC-aware.
    """

    async def record(self, entry: AuditEntry) -> None: ...

    def record_sync(self, entry: AuditEntry) -> None: ...

    async def entries(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        target: Target | None = None,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[AuditEntry]: ...

    def entries_sync(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        target: Target | None = None,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[AuditEntry]: ...

    async def prune(self, before: datetime) -> int: ...

    def prune_sync(self, before: datetime) -> int: ...


def matches(
    entry: AuditEntry,
    *,
    actor: str | None = None,
    action: str | None = None,
    target: Target | None = None,
    before: datetime | None = None,
) -> bool:
    """Whether `entry` passes entries()'s filters — the rule every store follows."""
    if actor is not None and entry.actor != actor:
        return False
    if action is not None:
        if action.endswith("."):
            if not entry.action.startswith(action):
                return False
        elif entry.action != action:
            return False
    if target is not None:
        target_type, target_id = target
        if entry.target_type != target_type:
            return False
        if target_id is not None and entry.target_id != str(target_id):
            return False
    return before is None or aware(entry.at) < aware(before)


def newest_first(entries: Iterable[AuditEntry]) -> list[AuditEntry]:
    """`entries` in entries() order."""
    return sorted(entries, key=lambda e: (aware(e.at), e.id), reverse=True)


class InMemoryAuditStore:
    """A process-local AuditStore — a list behind a lock. Nothing persists
    across restarts. The async methods delegate to the sync ones."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: list[AuditEntry] = []

    def record_sync(self, entry: AuditEntry) -> None:
        with self._lock:
            self._entries.append(replace(entry, at=aware(entry.at)))

    def entries_sync(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        target: Target | None = None,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[AuditEntry]:
        with self._lock:
            found = [
                e for e in self._entries
                if matches(e, actor=actor, action=action, target=target, before=before)
            ]
        return newest_first(found)[:limit]

    def prune_sync(self, before: datetime) -> int:
        cutoff = aware(before)
        with self._lock:
            kept = [e for e in self._entries if aware(e.at) >= cutoff]
            pruned = len(self._entries) - len(kept)
            self._entries = kept
            return pruned

    async def record(self, entry: AuditEntry) -> None:
        self.record_sync(entry)

    async def entries(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        target: Target | None = None,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[AuditEntry]:
        return self.entries_sync(
            actor=actor, action=action, target=target, before=before, limit=limit
        )

    async def prune(self, before: datetime) -> int:
        return self.prune_sync(before)
