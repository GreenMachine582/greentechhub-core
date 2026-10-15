"""testing.sqlalchemy — a pytest plugin of per-test database fixtures: one
SQLite file per test session, and every test inside a transaction that's
rolled back afterwards, so tests never see each other's rows, even when the
code under test commits.

    # conftest.py
    pytest_plugins = ["greentechhub_core.testing.sqlalchemy"]

    @pytest.fixture(scope="session")
    def gth_metadata():
        return SQLModel.metadata              # the tables to create

    @pytest.fixture(scope="session")
    def gth_session_class():
        return sqlmodel.ext.asyncio.session.AsyncSession

    async def test_something(gth_session, gth_database):
        with gth_database(db):                # the app's Database uses the test connection
            ...

Fixtures:
    gth_metadata: the MetaData whose tables are created (session scope;
        override it). Defaults to an empty one.
    gth_session_class: the AsyncSession class sessions are made from
        (session scope; override it, e.g. with SQLModel's).
    gth_engine: an aiosqlite engine on a temporary file, tables created
        (session scope).
    gth_connection: one connection per test, inside a transaction rolled
        back at the end.
    gth_sessionmaker: sessions on gth_connection; each one's commit only
        releases a SAVEPOINT, so the rollback still undoes it. A session
        that only read releases its SAVEPOINT on close too, so a write
        another session committed meanwhile (an audit store's, inside a
        route's request) isn't undone with it, as in production. One with
        uncommitted writes rolls them back, also as in production.
    gth_session: one session from gth_sessionmaker.
    gth_database: gth_database(db) is a context manager that points a
        greentechhub_core.sqlalchemy Database at gth_sessionmaker, and back
        again on exit.

Needs pytest-asyncio, SQLAlchemy and aiosqlite: the `[testing]` extra.
"""

from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from functools import cache
from typing import Any

try:
    import aiosqlite  # noqa: F401
    import pytest
    import pytest_asyncio
    from sqlalchemy import MetaData, event
    from sqlalchemy.ext.asyncio import (
        AsyncConnection,
        AsyncEngine,
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.orm import ORMExecuteState, Session
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "greentechhub_core.testing.sqlalchemy needs pytest-asyncio, SQLAlchemy and aiosqlite: "
        "pip install 'greentechhub-core[testing]'"
    ) from exc

from greentechhub_core.sqlalchemy.database import Database


@pytest.fixture(scope="session")
def gth_metadata() -> MetaData:
    return MetaData()


@pytest.fixture(scope="session")
def gth_session_class() -> type[AsyncSession]:
    return AsyncSession


@pytest_asyncio.fixture(scope="session")
async def gth_engine(
    tmp_path_factory: pytest.TempPathFactory, gth_metadata: MetaData
) -> AsyncIterator[AsyncEngine]:
    path = tmp_path_factory.mktemp("gth_db") / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")

    # pysqlite (under aiosqlite) runs its own BEGINs, which breaks SAVEPOINT
    # rollback; hand transaction control back to SQLAlchemy.
    # https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl
    @event.listens_for(engine.sync_engine, "connect")
    def _connect(dbapi_connection: Any, connection_record: Any) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(engine.sync_engine, "begin")
    def _begin(conn: Any) -> None:
        conn.exec_driver_sql("BEGIN")

    async with engine.begin() as conn:
        await conn.run_sync(gth_metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def gth_connection(gth_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with gth_engine.connect() as conn:
        await conn.begin()
        try:
            yield conn
        finally:
            await conn.rollback()


_WROTE = "gth_wrote"


@cache
def _releasing(sync_session_class: type[Session]) -> type[Session]:
    """`sync_session_class` (e.g. SQLModel's Session, keeping its exec()),
    except that closing it after only reading releases its SAVEPOINT rather
    than rolling back to it.

    Every session shares the test's one connection, so SAVEPOINTs nest: a
    store session's committed write inside a route session's still-open
    SAVEPOINT would be undone when the route session closes. A session
    counts as having written once it flushes or runs anything but a SELECT
    (text() included), and then closes with a rollback as before.
    """

    class ReleasingSession(sync_session_class):
        def close(self) -> None:
            pending = self.new or self.dirty or self.deleted
            if self.in_transaction() and not pending and not self.info.get(_WROTE):
                self.commit()
            super().close()

    def _executed(state: ORMExecuteState) -> None:
        if not state.is_select:
            state.session.info[_WROTE] = True

    def _flushed(session: Session, flush_context: Any) -> None:
        session.info[_WROTE] = True

    event.listen(ReleasingSession, "do_orm_execute", _executed)
    event.listen(ReleasingSession, "after_flush", _flushed)
    name = f"Releasing{sync_session_class.__name__}"
    ReleasingSession.__name__ = ReleasingSession.__qualname__ = name
    return ReleasingSession


@pytest.fixture
def gth_sessionmaker(
    gth_connection: AsyncConnection, gth_session_class: type[AsyncSession]
) -> async_sessionmaker:
    # Database.session_factory copies these options, sync_session_class
    # included, so the stores' sessions under gth_database release too.
    return async_sessionmaker(bind=gth_connection, class_=gth_session_class,
                              sync_session_class=_releasing(gth_session_class.sync_session_class),
                              join_transaction_mode="create_savepoint", expire_on_commit=False)


@pytest_asyncio.fixture
async def gth_session(gth_sessionmaker: async_sessionmaker) -> AsyncIterator[AsyncSession]:
    async with gth_sessionmaker() as session:
        yield session


@pytest.fixture
def gth_database(
    gth_sessionmaker: async_sessionmaker,
) -> Callable[[Database], AbstractContextManager[Database]]:
    @contextmanager
    def use(db: Database) -> Iterator[Database]:
        db.override(gth_sessionmaker)
        try:
            yield db
        finally:
            db.override(None)

    return use
