"""sqlalchemy.notifications — SQLAlchemyNotificationStore: a NotificationStore
(notifications.store) over the gth_notifications table
(tables.notifications_table).

Each call runs in its own transaction; marking read and pruning are single
UPDATE/DELETE statements scoped by recipient (and `read_at IS NULL`), so
the counts they return are exact even with other writers about.
"""

from collections.abc import Callable, Iterable
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from greentechhub_core.notifications.model import Notification, aware
from greentechhub_core.sqlalchemy._sessions import SessionFactories

_FIELDS = (
    "id", "recipient", "category", "kind", "title", "message", "icon",
    "action_label", "action_url", "created_at", "read_at",
)


class SQLAlchemyNotificationStore:
    """A NotificationStore over `table` (from notifications_table).

    Args:
        table: the gth_notifications Table on the service's metadata.
        session_factory: a sync session factory, for the `_sync` methods.
        async_session_factory: an async one, for the async methods.

    Give either factory or both.
    """

    def __init__(
        self,
        table: sa.Table,
        *,
        session_factory: Callable[[], Session] | None = None,
        async_session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._table = table
        self._sessions = SessionFactories(
            "SQLAlchemyNotificationStore", session_factory, async_session_factory
        )

    # statements

    def _insert(self, n: Notification) -> sa.Insert:
        values = {field: getattr(n, field) for field in _FIELDS}
        values["created_at"] = aware(n.created_at)
        values["read_at"] = aware(n.read_at) if n.read_at is not None else None
        return sa.insert(self._table).values(**values)

    def _list(self, recipient: str, unread_only: bool, limit: int) -> sa.Select:
        t = self._table.c
        stmt = sa.select(*(t[f] for f in _FIELDS)).where(t.recipient == recipient)
        if unread_only:
            stmt = stmt.where(t.read_at.is_(None))
        return stmt.order_by(t.created_at.desc(), t.id.desc()).limit(limit)

    def _unread(self, recipient: str) -> sa.Select:
        t = self._table.c
        return (
            sa.select(sa.func.count())
            .select_from(self._table)
            .where((t.recipient == recipient) & t.read_at.is_(None))
        )

    def _mark(self, recipient: str, ids: list[str] | None, at: datetime) -> sa.Update:
        t = self._table.c
        stmt = sa.update(self._table).where((t.recipient == recipient) & t.read_at.is_(None))
        if ids is not None:
            stmt = stmt.where(t.id.in_(ids))
        return stmt.values(read_at=aware(at))

    def _prune(self, before: datetime) -> sa.Delete:
        t = self._table.c
        return sa.delete(self._table).where(t.read_at.is_not(None) & (t.created_at < aware(before)))

    @staticmethod
    def _record(row) -> Notification:
        values = dict(row._mapping)
        values["created_at"] = aware(values["created_at"])
        if values["read_at"] is not None:
            values["read_at"] = aware(values["read_at"])
        return Notification(**values)

    # sync

    def add_sync(self, notification: Notification) -> None:
        with self._sessions.sync() as session, session.begin():
            session.execute(self._insert(notification))

    def list_for_sync(
        self, recipient: str, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]:
        with self._sessions.sync() as session:
            rows = session.execute(self._list(recipient, unread_only, limit))
            return [self._record(row) for row in rows]

    def unread_count_sync(self, recipient: str) -> int:
        with self._sessions.sync() as session:
            return session.execute(self._unread(recipient)).scalar_one()

    def mark_read_sync(self, recipient: str, ids: Iterable[str], *, at: datetime) -> int:
        ids = list(ids)
        if not ids:
            return 0
        with self._sessions.sync() as session, session.begin():
            return session.execute(self._mark(recipient, ids, at)).rowcount

    def mark_all_read_sync(self, recipient: str, *, at: datetime) -> int:
        with self._sessions.sync() as session, session.begin():
            return session.execute(self._mark(recipient, None, at)).rowcount

    def prune_sync(self, before: datetime) -> int:
        with self._sessions.sync() as session, session.begin():
            return session.execute(self._prune(before)).rowcount

    # async

    async def add(self, notification: Notification) -> None:
        async with self._sessions.async_() as session, session.begin():
            await session.execute(self._insert(notification))

    async def list_for(
        self, recipient: str, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]:
        async with self._sessions.async_() as session:
            rows = await session.execute(self._list(recipient, unread_only, limit))
            return [self._record(row) for row in rows]

    async def unread_count(self, recipient: str) -> int:
        async with self._sessions.async_() as session:
            return (await session.execute(self._unread(recipient))).scalar_one()

    async def mark_read(self, recipient: str, ids: Iterable[str], *, at: datetime) -> int:
        ids = list(ids)
        if not ids:
            return 0
        async with self._sessions.async_() as session, session.begin():
            return (await session.execute(self._mark(recipient, ids, at))).rowcount

    async def mark_all_read(self, recipient: str, *, at: datetime) -> int:
        async with self._sessions.async_() as session, session.begin():
            return (await session.execute(self._mark(recipient, None, at))).rowcount

    async def prune(self, before: datetime) -> int:
        async with self._sessions.async_() as session, session.begin():
            return (await session.execute(self._prune(before))).rowcount
