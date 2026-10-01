"""sqlalchemy.grants — SQLAlchemyGrantStore: a GrantStore over the
gth_role_grants table (tables.role_grants_table).

Each call runs in its own transaction. `assign` inserts only when the row
is missing; if a concurrent assign inserts it first, the IntegrityError
means the grant exists, which is what an idempotent assign wants.
"""

from collections.abc import Callable, Mapping

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from greentechhub_core.sqlalchemy._sessions import SessionFactories


class SQLAlchemyGrantStore:
    """A GrantStore over `table` (from role_grants_table).

    Args:
        table: the gth_role_grants Table on the service's metadata.
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
            "SQLAlchemyGrantStore", session_factory, async_session_factory
        )

    def _roles_for(self, subject: str) -> sa.Select:
        return sa.select(self._table.c.role).where(self._table.c.subject == subject)

    def _exists(self, subject: str, role: str) -> sa.Select:
        t = self._table.c
        return sa.select(t.role).where((t.subject == subject) & (t.role == role))

    def _insert(self, subject: str, role: str) -> sa.Insert:
        return sa.insert(self._table).values(subject=subject, role=role)

    def _delete(self, subject: str, role: str) -> sa.Delete:
        t = self._table.c
        return sa.delete(self._table).where((t.subject == subject) & (t.role == role))

    def _all(self) -> sa.Select:
        return sa.select(self._table.c.subject, self._table.c.role)

    @staticmethod
    def _group(rows) -> dict[str, frozenset[str]]:
        grouped: dict[str, set[str]] = {}
        for subject, role in rows:
            grouped.setdefault(subject, set()).add(role)
        return {subject: frozenset(roles) for subject, roles in grouped.items()}

    # sync

    def roles_for_sync(self, subject: str) -> frozenset[str]:
        with self._sessions.sync() as session:
            return frozenset(session.scalars(self._roles_for(subject)))

    def assign_sync(self, subject: str, role: str) -> None:
        try:
            with self._sessions.sync() as session, session.begin():
                if session.execute(self._exists(subject, role)).first() is None:
                    session.execute(self._insert(subject, role))
        except IntegrityError:
            pass  # a concurrent assign got there first

    def revoke_sync(self, subject: str, role: str) -> None:
        with self._sessions.sync() as session, session.begin():
            session.execute(self._delete(subject, role))

    def list_assignments_sync(self) -> Mapping[str, frozenset[str]]:
        with self._sessions.sync() as session:
            return self._group(session.execute(self._all()))

    # async

    async def roles_for(self, subject: str) -> frozenset[str]:
        async with self._sessions.async_() as session:
            return frozenset(await session.scalars(self._roles_for(subject)))

    async def assign(self, subject: str, role: str) -> None:
        try:
            async with self._sessions.async_() as session, session.begin():
                if (await session.execute(self._exists(subject, role))).first() is None:
                    await session.execute(self._insert(subject, role))
        except IntegrityError:
            pass  # a concurrent assign got there first

    async def revoke(self, subject: str, role: str) -> None:
        async with self._sessions.async_() as session, session.begin():
            await session.execute(self._delete(subject, role))

    async def list_assignments(self) -> Mapping[str, frozenset[str]]:
        async with self._sessions.async_() as session:
            return self._group(await session.execute(self._all()))
