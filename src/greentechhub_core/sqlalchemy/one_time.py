"""sqlalchemy.one_time — SQLAlchemyTokenStore: a TokenStore
(security.one_time) over the gth_one_time_tokens table
(tables.one_time_tokens_table).

Each call runs in its own transaction. `use` is a single
`UPDATE … WHERE used_at IS NULL`, so of two redeems racing for one token
exactly one sees its row change.
"""

from collections.abc import Callable
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from greentechhub_core.security.one_time import TokenRecord
from greentechhub_core.security.throttle import aware
from greentechhub_core.sqlalchemy._sessions import SessionFactories

_FIELDS = ("token_hash", "purpose", "subject", "created_at", "expires_at", "used_at")


class SQLAlchemyTokenStore:
    """A TokenStore over `table` (from one_time_tokens_table).

    Args:
        table: the gth_one_time_tokens Table on the service's metadata.
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
            "SQLAlchemyTokenStore", session_factory, async_session_factory
        )

    # statements

    def _insert(self, r: TokenRecord) -> sa.Insert:
        return sa.insert(self._table).values(
            token_hash=r.token_hash, purpose=r.purpose, subject=r.subject,
            created_at=aware(r.created_at), expires_at=aware(r.expires_at),
            used_at=aware(r.used_at) if r.used_at is not None else None,
        )

    def _select(self, token_hash: str) -> sa.Select:
        t = self._table.c
        return sa.select(*(t[f] for f in _FIELDS)).where(t.token_hash == token_hash)

    def _use(self, token_hash: str, at: datetime) -> sa.Update:
        t = self._table.c
        return (
            sa.update(self._table)
            .where((t.token_hash == token_hash) & t.used_at.is_(None))
            .values(used_at=aware(at))
        )

    def _revoke(self, subject: str, purpose: str) -> sa.Delete:
        t = self._table.c
        return sa.delete(self._table).where(
            (t.subject == subject) & (t.purpose == purpose) & t.used_at.is_(None)
        )

    def _prune(self, before: datetime) -> sa.Delete:
        t = self._table.c
        before = aware(before)
        return sa.delete(self._table).where(
            (t.expires_at < before) | (t.used_at.is_not(None) & (t.used_at < before))
        )

    @staticmethod
    def _record(row) -> TokenRecord | None:
        if row is None:
            return None
        values = dict(row._mapping)
        for field in ("created_at", "expires_at", "used_at"):
            if values[field] is not None:
                values[field] = aware(values[field])
        return TokenRecord(**values)

    # sync

    def add_sync(self, record: TokenRecord) -> None:
        with self._sessions.sync() as session, session.begin():
            session.execute(self._insert(record))

    def get_sync(self, token_hash: str) -> TokenRecord | None:
        with self._sessions.sync() as session:
            return self._record(session.execute(self._select(token_hash)).first())

    def use_sync(self, token_hash: str, at: datetime) -> bool:
        with self._sessions.sync() as session, session.begin():
            return session.execute(self._use(token_hash, at)).rowcount == 1

    def revoke_sync(self, subject: str, purpose: str) -> int:
        with self._sessions.sync() as session, session.begin():
            return session.execute(self._revoke(subject, purpose)).rowcount

    def prune_sync(self, before: datetime) -> int:
        with self._sessions.sync() as session, session.begin():
            return session.execute(self._prune(before)).rowcount

    # async

    async def add(self, record: TokenRecord) -> None:
        async with self._sessions.async_() as session, session.begin():
            await session.execute(self._insert(record))

    async def get(self, token_hash: str) -> TokenRecord | None:
        async with self._sessions.async_() as session:
            return self._record((await session.execute(self._select(token_hash))).first())

    async def use(self, token_hash: str, at: datetime) -> bool:
        async with self._sessions.async_() as session, session.begin():
            return (await session.execute(self._use(token_hash, at))).rowcount == 1

    async def revoke(self, subject: str, purpose: str) -> int:
        async with self._sessions.async_() as session, session.begin():
            return (await session.execute(self._revoke(subject, purpose))).rowcount

    async def prune(self, before: datetime) -> int:
        async with self._sessions.async_() as session, session.begin():
            return (await session.execute(self._prune(before))).rowcount
