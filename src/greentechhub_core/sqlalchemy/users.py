"""sqlalchemy.users — SQLAlchemyUserStore: a UserStore (users.store) over the
gth_users and gth_user_identities tables (tables.users_table,
tables.user_identities_table).

Each call runs in its own transaction. `create` with a link inserts both
rows in one, so a sign-in never leaves an unlinked account behind. Clashes
are checked before writing, and a unique-constraint failure from a
concurrent writer is caught and reported the same way (UserExists or
LinkExists) once the transaction has rolled back.
"""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from greentechhub_core.security.throttle import aware
from greentechhub_core.sqlalchemy._sessions import SessionFactories
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

_USER_FIELDS = ("id", "username", "email", "email_verified", "display_name", "active",
                "password_hash", "auth_source", "created_at", "updated_at", "last_login_at")
_LINK_FIELDS = ("provider", "external_subject", "user_id", "created_at", "last_seen_at")
_USER_TIMES = ("created_at", "updated_at", "last_login_at")
_LINK_TIMES = ("created_at", "last_seen_at")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _or_none(normalize: Callable[[str], str | None], value: str) -> str | None:
    try:
        return normalize(value)
    except ValueError:
        return None


class SQLAlchemyUserStore:
    """A UserStore over `users` and `identities` (from users_table and
    user_identities_table).

    Args:
        users: the gth_users Table on the service's metadata.
        identities: the gth_user_identities Table.
        session_factory: a sync session factory, for the `_sync` methods.
        async_session_factory: an async one, for the async methods.
        clock: returns the current time; tests pass a fake one.

    Give either factory or both.
    """

    def __init__(
        self,
        users: sa.Table,
        identities: sa.Table,
        *,
        session_factory: Callable[[], Session] | None = None,
        async_session_factory: Callable[[], AsyncSession] | None = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._users = users
        self._identities = identities
        self._sessions = SessionFactories(
            "SQLAlchemyUserStore", session_factory, async_session_factory
        )
        self._clock = clock

    def now(self) -> datetime:
        return aware(self._clock())

    # statements

    def _select_users(self) -> sa.Select:
        u = self._users.c
        return sa.select(*(u[f] for f in _USER_FIELDS))

    def _select_user(self, column: str, value: str | None) -> sa.Select:
        return self._select_users().where(self._users.c[column] == value)

    def _select_link(self, provider: str, external_subject: str) -> sa.Select:
        i = self._identities.c
        return sa.select(*(i[f] for f in _LINK_FIELDS)).where(
            (i.provider == provider) & (i.external_subject == external_subject)
        )

    def _select_links_for(self, user_id: str) -> sa.Select:
        i = self._identities.c
        return (sa.select(*(i[f] for f in _LINK_FIELDS)).where(i.user_id == user_id)
                .order_by(i.created_at, i.provider))

    def _clash(self, account: UserAccount) -> sa.Select:
        """The usernames and emails other accounts hold that `account` would repeat."""
        u = self._users.c
        condition = u.username == account.username
        if account.email is not None:
            condition = condition | (u.email == account.email)
        return sa.select(u.username, u.email).where(condition & (u.id != account.id)).limit(1)

    def _insert_user(self, a: UserAccount) -> sa.Insert:
        return sa.insert(self._users).values({f: getattr(a, f) for f in _USER_FIELDS})

    def _insert_link(self, link: LinkedIdentity) -> sa.Insert:
        return sa.insert(self._identities).values({f: getattr(link, f) for f in _LINK_FIELDS})

    def _update_user(self, a: UserAccount) -> sa.Update:
        values = {f: getattr(a, f) for f in _USER_FIELDS if f != "id"}
        return sa.update(self._users).where(self._users.c.id == a.id).values(values)

    def _touch(self, provider: str, external_subject: str) -> sa.Update:
        i = self._identities.c
        return (sa.update(self._identities)
                .where((i.provider == provider) & (i.external_subject == external_subject))
                .values(last_seen_at=self.now()))

    def _delete_link(self, provider: str, external_subject: str) -> sa.Delete:
        i = self._identities.c
        return sa.delete(self._identities).where(
            (i.provider == provider) & (i.external_subject == external_subject)
        )

    def _new_link(self, user_id: str, provider: str, external_subject: str) -> LinkedIdentity:
        return LinkedIdentity(provider=provider, external_subject=external_subject,
                              user_id=user_id, created_at=self.now())

    @staticmethod
    def _raise_clash(account: UserAccount, row) -> None:
        if row is None:
            return
        if row.username == account.username:
            raise UserExists("username", account.username)
        raise UserExists("email", account.email or "")

    @staticmethod
    def _account(row) -> UserAccount | None:
        if row is None:
            return None
        values = dict(row._mapping)
        for field in _USER_TIMES:
            if values[field] is not None:
                values[field] = aware(values[field])
        return UserAccount(**values)

    @staticmethod
    def _link(row) -> LinkedIdentity | None:
        if row is None:
            return None
        values = dict(row._mapping)
        for field in _LINK_TIMES:
            if values[field] is not None:
                values[field] = aware(values[field])
        return LinkedIdentity(**values)

    # sync

    def _classify_sync(self, account: UserAccount, link: tuple[str, str] | None) -> None:
        """After an IntegrityError: raise what the concurrent writer took."""
        with self._sessions.sync() as session:
            self._raise_clash(account, session.execute(self._clash(account)).first())
            if link is not None and session.execute(self._select_link(*link)).first():
                raise LinkExists(f"{link[0]}:{link[1]} is already linked")

    def create_sync(
        self, username: str, *, link: tuple[str, str] | None = None, **fields: Any
    ) -> UserAccount:
        account = new_account(username, now=self.now(), **fields)
        try:
            with self._sessions.sync() as session, session.begin():
                self._raise_clash(account, session.execute(self._clash(account)).first())
                if link is not None and session.execute(self._select_link(*link)).first():
                    raise LinkExists(f"{link[0]}:{link[1]} is already linked")
                session.execute(self._insert_user(account))
                if link is not None:
                    session.execute(self._insert_link(self._new_link(account.id, *link)))
        except IntegrityError:
            self._classify_sync(account, link)
            raise
        return account

    def get_sync(self, user_id: str) -> UserAccount | None:
        with self._sessions.sync() as session:
            return self._account(session.execute(self._select_user("id", user_id)).first())

    def by_username_sync(self, username: str) -> UserAccount | None:
        value = _or_none(normalize_username, username)
        if value is None:
            return None
        with self._sessions.sync() as session:
            return self._account(session.execute(self._select_user("username", value)).first())

    def by_email_sync(self, email: str) -> UserAccount | None:
        value = _or_none(normalize_email, email)
        if value is None:
            return None
        with self._sessions.sync() as session:
            return self._account(session.execute(self._select_user("email", value)).first())

    def list_users_sync(self) -> list[UserAccount]:
        with self._sessions.sync() as session:
            rows = session.execute(self._select_users().order_by(self._users.c.username))
            return [self._account(row) for row in rows]

    def update_sync(self, user_id: str, changes: Mapping[str, Any]) -> UserAccount | None:
        try:
            with self._sessions.sync() as session, session.begin():
                current = self._account(session.execute(self._select_user("id", user_id)).first())
                if current is None:
                    return None
                updated = apply_changes(current, changes, now=self.now())
                self._raise_clash(updated, session.execute(self._clash(updated)).first())
                session.execute(self._update_user(updated))
        except IntegrityError:
            self._classify_sync(updated, None)
            raise
        return updated

    def link_sync(self, user_id: str, provider: str, external_subject: str) -> LinkedIdentity:
        link = self._new_link(user_id, provider, external_subject)
        try:
            with self._sessions.sync() as session, session.begin():
                if session.execute(self._select_user("id", user_id)).first() is None:
                    raise KeyError(user_id)
                if session.execute(self._select_link(provider, external_subject)).first():
                    raise LinkExists(f"{provider}:{external_subject} is already linked")
                session.execute(self._insert_link(link))
        except IntegrityError as exc:
            raise LinkExists(f"{provider}:{external_subject} is already linked") from exc
        return link

    def find_link_sync(self, provider: str, external_subject: str) -> LinkedIdentity | None:
        with self._sessions.sync() as session:
            row = session.execute(self._select_link(provider, external_subject)).first()
            return self._link(row)

    def links_for_sync(self, user_id: str) -> list[LinkedIdentity]:
        with self._sessions.sync() as session:
            return [self._link(row) for row in session.execute(self._select_links_for(user_id))]

    def touch_link_sync(self, provider: str, external_subject: str) -> None:
        with self._sessions.sync() as session, session.begin():
            session.execute(self._touch(provider, external_subject))

    def unlink_sync(self, provider: str, external_subject: str) -> bool:
        with self._sessions.sync() as session, session.begin():
            return session.execute(self._delete_link(provider, external_subject)).rowcount == 1

    # async

    async def _classify(self, account: UserAccount, link: tuple[str, str] | None) -> None:
        async with self._sessions.async_() as session:
            self._raise_clash(account, (await session.execute(self._clash(account))).first())
            if link is not None and (await session.execute(self._select_link(*link))).first():
                raise LinkExists(f"{link[0]}:{link[1]} is already linked")

    async def create(
        self, username: str, *, link: tuple[str, str] | None = None, **fields: Any
    ) -> UserAccount:
        account = new_account(username, now=self.now(), **fields)
        try:
            async with self._sessions.async_() as session, session.begin():
                clash = (await session.execute(self._clash(account))).first()
                self._raise_clash(account, clash)
                if link is not None and (await session.execute(self._select_link(*link))).first():
                    raise LinkExists(f"{link[0]}:{link[1]} is already linked")
                await session.execute(self._insert_user(account))
                if link is not None:
                    await session.execute(self._insert_link(self._new_link(account.id, *link)))
        except IntegrityError:
            await self._classify(account, link)
            raise
        return account

    async def get(self, user_id: str) -> UserAccount | None:
        async with self._sessions.async_() as session:
            return self._account((await session.execute(self._select_user("id", user_id))).first())

    async def by_username(self, username: str) -> UserAccount | None:
        value = _or_none(normalize_username, username)
        if value is None:
            return None
        async with self._sessions.async_() as session:
            row = (await session.execute(self._select_user("username", value))).first()
            return self._account(row)

    async def by_email(self, email: str) -> UserAccount | None:
        value = _or_none(normalize_email, email)
        if value is None:
            return None
        async with self._sessions.async_() as session:
            return self._account((await session.execute(self._select_user("email", value))).first())

    async def list_users(self) -> list[UserAccount]:
        async with self._sessions.async_() as session:
            rows = await session.execute(self._select_users().order_by(self._users.c.username))
            return [self._account(row) for row in rows]

    async def update(self, user_id: str, changes: Mapping[str, Any]) -> UserAccount | None:
        try:
            async with self._sessions.async_() as session, session.begin():
                row = (await session.execute(self._select_user("id", user_id))).first()
                current = self._account(row)
                if current is None:
                    return None
                updated = apply_changes(current, changes, now=self.now())
                self._raise_clash(updated, (await session.execute(self._clash(updated))).first())
                await session.execute(self._update_user(updated))
        except IntegrityError:
            await self._classify(updated, None)
            raise
        return updated

    async def link(self, user_id: str, provider: str, external_subject: str) -> LinkedIdentity:
        link = self._new_link(user_id, provider, external_subject)
        try:
            async with self._sessions.async_() as session, session.begin():
                if (await session.execute(self._select_user("id", user_id))).first() is None:
                    raise KeyError(user_id)
                if (await session.execute(self._select_link(provider, external_subject))).first():
                    raise LinkExists(f"{provider}:{external_subject} is already linked")
                await session.execute(self._insert_link(link))
        except IntegrityError as exc:
            raise LinkExists(f"{provider}:{external_subject} is already linked") from exc
        return link

    async def find_link(self, provider: str, external_subject: str) -> LinkedIdentity | None:
        async with self._sessions.async_() as session:
            row = (await session.execute(self._select_link(provider, external_subject))).first()
            return self._link(row)

    async def links_for(self, user_id: str) -> list[LinkedIdentity]:
        async with self._sessions.async_() as session:
            rows = await session.execute(self._select_links_for(user_id))
            return [self._link(row) for row in rows]

    async def touch_link(self, provider: str, external_subject: str) -> None:
        async with self._sessions.async_() as session, session.begin():
            await session.execute(self._touch(provider, external_subject))

    async def unlink(self, provider: str, external_subject: str) -> bool:
        async with self._sessions.async_() as session, session.begin():
            result = await session.execute(self._delete_link(provider, external_subject))
            return result.rowcount == 1
