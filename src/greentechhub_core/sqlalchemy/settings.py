"""sqlalchemy.settings — SQLAlchemySettingsStore: a SettingsStore over the
gth_settings table (tables.settings_table).

Each call runs in its own transaction from the given session factory.
`set` is an update-then-insert, which works on every backend; if a
concurrent writer inserts the same row first, the resulting IntegrityError
is caught and the write retried once, which then takes the update path.
"""

from collections.abc import Callable

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from greentechhub_core.settings import SettingScope, SettingValue, check_owner
from greentechhub_core.sqlalchemy._sessions import SessionFactories
from greentechhub_core.sqlalchemy.tables import APP_SUBJECT


class SQLAlchemySettingsStore:
    """A SettingsStore over `table` (from settings_table).

    Args:
        table: the gth_settings Table on the service's metadata.
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
            "SQLAlchemySettingsStore", session_factory, async_session_factory
        )

    def _owner(self, scope: SettingScope, subject: str | None):
        scope = check_owner(scope, subject)
        t = self._table.c
        return (t.scope == scope.value) & (t.subject == (subject or APP_SUBJECT))

    def _select(self, scope: SettingScope, subject: str | None) -> sa.Select:
        t = self._table.c
        return sa.select(t.key, t.value).where(self._owner(scope, subject))

    def _update(self, scope, subject, key: str, value: SettingValue) -> sa.Update:
        where = self._owner(scope, subject) & (self._table.c.key == key)
        return sa.update(self._table).where(where).values(value=value)

    def _insert(self, scope, subject, key: str, value: SettingValue) -> sa.Insert:
        return sa.insert(self._table).values(
            scope=SettingScope(scope).value,
            subject=subject or APP_SUBJECT,
            key=key,
            value=value,
        )

    def _delete(self, scope, subject, key: str) -> sa.Delete:
        where = self._owner(scope, subject) & (self._table.c.key == key)
        return sa.delete(self._table).where(where)

    # sync

    def get_many_sync(self, scope: SettingScope, subject: str | None) -> dict[str, SettingValue]:
        statement = self._select(scope, subject)
        with self._sessions.sync() as session:
            return {key: value for key, value in session.execute(statement)}

    def set_sync(
        self, scope: SettingScope, subject: str | None, key: str, value: SettingValue
    ) -> None:
        update = self._update(scope, subject, key, value)
        for attempt in range(2):
            try:
                with self._sessions.sync() as session, session.begin():
                    if not session.execute(update).rowcount:
                        session.execute(self._insert(scope, subject, key, value))
                return
            except IntegrityError:
                if attempt:
                    raise

    def delete_sync(self, scope: SettingScope, subject: str | None, key: str) -> None:
        statement = self._delete(scope, subject, key)
        with self._sessions.sync() as session, session.begin():
            session.execute(statement)

    # async

    async def get_many(self, scope: SettingScope, subject: str | None) -> dict[str, SettingValue]:
        statement = self._select(scope, subject)
        async with self._sessions.async_() as session:
            return {key: value for key, value in await session.execute(statement)}

    async def set(
        self, scope: SettingScope, subject: str | None, key: str, value: SettingValue
    ) -> None:
        update = self._update(scope, subject, key, value)
        for attempt in range(2):
            try:
                async with self._sessions.async_() as session, session.begin():
                    if not (await session.execute(update)).rowcount:
                        await session.execute(self._insert(scope, subject, key, value))
                return
            except IntegrityError:
                if attempt:
                    raise

    async def delete(self, scope: SettingScope, subject: str | None, key: str) -> None:
        statement = self._delete(scope, subject, key)
        async with self._sessions.async_() as session, session.begin():
            await session.execute(statement)
