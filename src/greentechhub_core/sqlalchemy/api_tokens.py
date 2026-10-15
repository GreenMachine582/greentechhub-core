"""sqlalchemy.api_tokens — SQLAlchemyApiTokenStore: an ApiTokenStore
(security.api_tokens) over the gth_api_tokens table
(tables.api_tokens_table).

Each call runs in its own transaction. `verify` updates last_used_at with
`UPDATE … WHERE token_hash = … AND (expires_at IS NULL OR expires_at > now)`
and reads the row back only if that changed it, so a token revoked or
expired between the two never verifies.
"""

from collections.abc import Callable, Iterable
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from greentechhub_core.security.api_tokens import ApiToken, new_api_token
from greentechhub_core.security.one_time import token_hash
from greentechhub_core.security.throttle import aware
from greentechhub_core.sqlalchemy._sessions import SessionFactories

_FIELDS = ("id", "owner", "name", "scopes", "token_hash", "created_at", "expires_at",
           "last_used_at")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SQLAlchemyApiTokenStore:
    """An ApiTokenStore over `table` (from api_tokens_table).

    Args:
        table: the gth_api_tokens Table on the service's metadata.
        session_factory: a sync session factory, for the `_sync` methods.
        async_session_factory: an async one, for the async methods.
        clock: returns the current time; tests pass a fake one.

    Give either factory or both.
    """

    def __init__(
        self,
        table: sa.Table,
        *,
        session_factory: Callable[[], Session] | None = None,
        async_session_factory: Callable[[], AsyncSession] | None = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._table = table
        self._sessions = SessionFactories(
            "SQLAlchemyApiTokenStore", session_factory, async_session_factory
        )
        self._clock = clock

    def _new(self, owner: str, name: str, scopes: Iterable[str],
             expires_at: datetime | None) -> tuple[ApiToken, str]:
        return new_api_token(owner, name, scopes, now=self._clock(), expires_at=expires_at)

    # statements

    def _insert(self, t: ApiToken) -> sa.Insert:
        return sa.insert(self._table).values(
            id=t.id, owner=t.owner, name=t.name, scopes=sorted(t.scopes), token_hash=t.token_hash,
            created_at=t.created_at, expires_at=t.expires_at, last_used_at=t.last_used_at,
        )

    def _touch(self, plaintext: str, now: datetime) -> sa.Update:
        t = self._table.c
        return (
            sa.update(self._table)
            .where((t.token_hash == token_hash(plaintext))
                   & (t.expires_at.is_(None) | (t.expires_at > now)))
            .values(last_used_at=now)
        )

    def _select_by_hash(self, plaintext: str) -> sa.Select:
        t = self._table.c
        return sa.select(*(t[f] for f in _FIELDS)).where(t.token_hash == token_hash(plaintext))

    def _select_for(self, owner: str) -> sa.Select:
        t = self._table.c
        return (
            sa.select(*(t[f] for f in _FIELDS))
            .where(t.owner == owner)
            .order_by(t.created_at.desc(), t.id.desc())
        )

    def _delete(self, token_id: str, owner: str | None) -> sa.Delete:
        t = self._table.c
        condition = t.id == token_id
        if owner is not None:
            condition = condition & (t.owner == owner)
        return sa.delete(self._table).where(condition)

    @staticmethod
    def _token(row) -> ApiToken | None:
        if row is None:
            return None
        values = dict(row._mapping)
        values["scopes"] = frozenset(values["scopes"])
        for field in ("created_at", "expires_at", "last_used_at"):
            if values[field] is not None:
                values[field] = aware(values[field])
        return ApiToken(**values)

    # sync

    def create_sync(
        self, owner: str, name: str, scopes: Iterable[str], expires_at: datetime | None = None
    ) -> tuple[ApiToken, str]:
        token, plaintext = self._new(owner, name, scopes, expires_at)
        with self._sessions.sync() as session, session.begin():
            session.execute(self._insert(token))
        return token, plaintext

    def verify_sync(self, plaintext: str) -> ApiToken | None:
        now = aware(self._clock())
        with self._sessions.sync() as session, session.begin():
            if session.execute(self._touch(plaintext, now)).rowcount != 1:
                return None
            return self._token(session.execute(self._select_by_hash(plaintext)).first())

    def list_for_sync(self, owner: str) -> list[ApiToken]:
        with self._sessions.sync() as session:
            return [self._token(row) for row in session.execute(self._select_for(owner))]

    def revoke_sync(self, token_id: str, owner: str | None = None) -> bool:
        with self._sessions.sync() as session, session.begin():
            return session.execute(self._delete(token_id, owner)).rowcount == 1

    # async

    async def create(
        self, owner: str, name: str, scopes: Iterable[str], expires_at: datetime | None = None
    ) -> tuple[ApiToken, str]:
        token, plaintext = self._new(owner, name, scopes, expires_at)
        async with self._sessions.async_() as session, session.begin():
            await session.execute(self._insert(token))
        return token, plaintext

    async def verify(self, plaintext: str) -> ApiToken | None:
        now = aware(self._clock())
        async with self._sessions.async_() as session, session.begin():
            if (await session.execute(self._touch(plaintext, now))).rowcount != 1:
                return None
            return self._token((await session.execute(self._select_by_hash(plaintext))).first())

    async def list_for(self, owner: str) -> list[ApiToken]:
        async with self._sessions.async_() as session:
            return [self._token(row) for row in await session.execute(self._select_for(owner))]

    async def revoke(self, token_id: str, owner: str | None = None) -> bool:
        async with self._sessions.async_() as session, session.begin():
            return (await session.execute(self._delete(token_id, owner))).rowcount == 1
