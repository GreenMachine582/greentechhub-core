"""sqlalchemy.audit — SQLAlchemyAuditStore: an AuditStore (audit.store) over
the gth_audit_log table (tables.audit_log_table).

Each call runs in its own transaction; list() turns its filters into WHERE
clauses (an action prefix into a LIKE), so filtering happens in the
database.
"""

from collections.abc import Callable
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from greentechhub_core.audit.model import AuditEntry
from greentechhub_core.audit.store import Target
from greentechhub_core.security.throttle import aware
from greentechhub_core.sqlalchemy._sessions import SessionFactories

_FIELDS = ("id", "at", "actor", "action", "target_type", "target_id", "summary", "details")


def _like(prefix: str) -> str:
    return prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


class SQLAlchemyAuditStore:
    """An AuditStore over `table` (from audit_log_table).

    Args:
        table: the gth_audit_log Table on the service's metadata.
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
            "SQLAlchemyAuditStore", session_factory, async_session_factory
        )

    # statements

    def _insert(self, e: AuditEntry) -> sa.Insert:
        values = {f: getattr(e, f) for f in _FIELDS}
        values["at"] = aware(e.at)
        values["details"] = dict(e.details)
        return sa.insert(self._table).values(**values)

    def _list(self, actor, action, target: Target | None, before, limit: int) -> sa.Select:
        t = self._table.c
        stmt = sa.select(*(t[f] for f in _FIELDS))
        if actor is not None:
            stmt = stmt.where(t.actor == actor)
        if action is not None and action.endswith("."):
            stmt = stmt.where(t.action.like(_like(action), escape="\\"))
        elif action is not None:
            stmt = stmt.where(t.action == action)
        if target is not None:
            target_type, target_id = target
            stmt = stmt.where(t.target_type == target_type)
            if target_id is not None:
                stmt = stmt.where(t.target_id == str(target_id))
        if before is not None:
            stmt = stmt.where(t.at < aware(before))
        return stmt.order_by(t.at.desc(), t.id.desc()).limit(limit)

    def _prune(self, before: datetime) -> sa.Delete:
        return sa.delete(self._table).where(self._table.c.at < aware(before))

    @staticmethod
    def _entry(row) -> AuditEntry:
        values = dict(row._mapping)
        values["at"] = aware(values["at"])
        values["details"] = values["details"] or {}
        return AuditEntry(**values)

    # sync

    def record_sync(self, entry: AuditEntry) -> None:
        with self._sessions.sync() as session, session.begin():
            session.execute(self._insert(entry))

    def list_sync(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        target: Target | None = None,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[AuditEntry]:
        with self._sessions.sync() as session:
            rows = session.execute(self._list(actor, action, target, before, limit))
            return [self._entry(row) for row in rows]

    def prune_sync(self, before: datetime) -> int:
        with self._sessions.sync() as session, session.begin():
            return session.execute(self._prune(before)).rowcount

    # async

    async def record(self, entry: AuditEntry) -> None:
        async with self._sessions.async_() as session, session.begin():
            await session.execute(self._insert(entry))

    async def list(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        target: Target | None = None,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[AuditEntry]:
        async with self._sessions.async_() as session:
            rows = await session.execute(self._list(actor, action, target, before, limit))
            return [self._entry(row) for row in rows]

    async def prune(self, before: datetime) -> int:
        async with self._sessions.async_() as session, session.begin():
            return (await session.execute(self._prune(before))).rowcount
