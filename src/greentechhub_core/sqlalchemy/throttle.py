"""sqlalchemy.throttle — SQLAlchemyAttemptStore: an AttemptStore
(security.throttle) over the gth_login_attempts table
(tables.login_attempts_table), so every worker of a service shares one
count.

Each call runs in its own transaction. Within a window, `hit` raises the
count with `failures = failures + 1` in the database, so two failures at
once both count; a new key whose insert loses a race to a concurrent hit
retries once and then counts on the row the other one wrote.
"""

from collections.abc import Callable
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from greentechhub_core.security.throttle import Attempts, aware, next_attempts
from greentechhub_core.sqlalchemy._sessions import SessionFactories


class SQLAlchemyAttemptStore:
    """An AttemptStore over `table` (from login_attempts_table).

    Args:
        table: the gth_login_attempts Table on the service's metadata.
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
            "SQLAlchemyAttemptStore", session_factory, async_session_factory
        )

    # statements

    def _select(self, key: str) -> sa.Select:
        t = self._table.c
        return sa.select(t.key, t.failures, t.window_start, t.locked_until).where(t.key == key)

    def _insert(self, record: Attempts) -> sa.Insert:
        return sa.insert(self._table).values(
            key=record.key,
            failures=record.failures,
            window_start=record.window_start,
            locked_until=record.locked_until,
        )

    def _restart(self, record: Attempts) -> sa.Update:
        t = self._table.c
        return (
            sa.update(self._table)
            .where(t.key == record.key)
            .values(failures=1, window_start=record.window_start, locked_until=record.locked_until)
        )

    def _increment(self, key: str) -> sa.Update:
        t = self._table.c
        return sa.update(self._table).where(t.key == key).values(failures=t.failures + 1)

    def _set_lock(self, key: str, until: datetime) -> sa.Update:
        return sa.update(self._table).where(self._table.c.key == key).values(locked_until=until)

    def _delete(self, key: str) -> sa.Delete:
        return sa.delete(self._table).where(self._table.c.key == key)

    def _stale(self, before: datetime) -> sa.Delete:
        t = self._table.c
        before = aware(before)
        return sa.delete(self._table).where(
            (t.window_start < before) & ((t.locked_until.is_(None)) | (t.locked_until < before))
        )

    @staticmethod
    def _lock_only(key: str, until: datetime) -> Attempts:
        return Attempts(key=key, failures=0, window_start=until, locked_until=until)

    @staticmethod
    def _record(row) -> Attempts | None:
        if row is None:
            return None
        return Attempts(
            key=row.key,
            failures=row.failures,
            window_start=aware(row.window_start),
            locked_until=aware(row.locked_until) if row.locked_until is not None else None,
        )

    def _plan(self, current: Attempts | None, key: str, now: datetime, window: timedelta):
        """The statement `hit` runs, given the row as it stands."""
        record = next_attempts(current, key, now, window)
        if current is None:
            return self._insert(record)
        if record.failures == 1:
            return self._restart(record)
        return self._increment(key)

    # sync

    def get_sync(self, key: str) -> Attempts | None:
        with self._sessions.sync() as session:
            return self._record(session.execute(self._select(key)).first())

    def hit_sync(self, key: str, now: datetime, window: timedelta) -> Attempts:
        for attempt in range(2):
            try:
                with self._sessions.sync() as session, session.begin():
                    current = self._record(session.execute(self._select(key)).first())
                    session.execute(self._plan(current, key, now, window))
                    record = self._record(session.execute(self._select(key)).first())
                assert record is not None
                return record
            except IntegrityError:
                if attempt:
                    raise  # pragma: no cover - a second lost insert race
        raise AssertionError("unreachable")  # pragma: no cover

    def lock_sync(self, key: str, until: datetime) -> None:
        until = aware(until)
        with self._sessions.sync() as session, session.begin():
            if session.execute(self._set_lock(key, until)).rowcount == 0:
                session.execute(
                    self._insert(self._lock_only(key, until))
                )

    def clear_sync(self, key: str) -> None:
        with self._sessions.sync() as session, session.begin():
            session.execute(self._delete(key))

    def prune_sync(self, before: datetime) -> int:
        with self._sessions.sync() as session, session.begin():
            return session.execute(self._stale(before)).rowcount

    # async

    async def get(self, key: str) -> Attempts | None:
        async with self._sessions.async_() as session:
            return self._record((await session.execute(self._select(key))).first())

    async def hit(self, key: str, now: datetime, window: timedelta) -> Attempts:
        for attempt in range(2):
            try:
                async with self._sessions.async_() as session, session.begin():
                    current = self._record((await session.execute(self._select(key))).first())
                    await session.execute(self._plan(current, key, now, window))
                    record = self._record((await session.execute(self._select(key))).first())
                assert record is not None
                return record
            except IntegrityError:
                if attempt:
                    raise  # pragma: no cover - a second lost insert race
        raise AssertionError("unreachable")  # pragma: no cover

    async def lock(self, key: str, until: datetime) -> None:
        until = aware(until)
        async with self._sessions.async_() as session, session.begin():
            if (await session.execute(self._set_lock(key, until))).rowcount == 0:
                await session.execute(
                    self._insert(self._lock_only(key, until))
                )

    async def clear(self, key: str) -> None:
        async with self._sessions.async_() as session, session.begin():
            await session.execute(self._delete(key))

    async def prune(self, before: datetime) -> int:
        async with self._sessions.async_() as session, session.begin():
            return (await session.execute(self._stale(before))).rowcount

