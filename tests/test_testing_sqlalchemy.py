"""testing.sqlalchemy: the per-test database fixtures, run in an inner pytest
session the way a service's conftest loads them — each test's rows are rolled
back (even after a commit), gth_metadata picks the tables, and gth_database
points a Database at the test connection and back."""

import pytest

pytest_plugins = ["pytester"]

CONFTEST = '''
import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table

pytest_plugins = ["greentechhub_core.testing.sqlalchemy"]

METADATA = MetaData()
NOTES = Table("notes", METADATA, Column("id", Integer, primary_key=True), Column("text", String))


@pytest.fixture(scope="session")
def gth_metadata():
    return METADATA
'''


def _run(pytester: pytest.Pytester, tests: str) -> pytest.RunResult:
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makeconftest(CONFTEST)
    pytester.makepyfile(tests)
    return pytester.runpytest_subprocess("-p", "no:cacheprovider")


def test_each_test_starts_empty_even_after_a_commit(pytester: pytest.Pytester):
    result = _run(pytester, '''
from sqlalchemy import func, select
from conftest import NOTES


async def _count(session):
    return (await session.execute(select(func.count()).select_from(NOTES))).scalar_one()


async def test_a_writes_and_commits(gth_session):
    await gth_session.execute(NOTES.insert().values(text="a"))
    await gth_session.commit()
    assert await _count(gth_session) == 1


async def test_b_sees_nothing(gth_session):
    assert await _count(gth_session) == 0


async def test_c_sessions_share_the_connection(gth_sessionmaker):
    async with gth_sessionmaker() as first:
        await first.execute(NOTES.insert().values(text="c"))
        await first.commit()
    async with gth_sessionmaker() as second:
        assert await _count(second) == 1
''')
    result.assert_outcomes(passed=3)


def test_gth_database_overrides_a_database_and_resets_it(pytester: pytest.Pytester):
    result = _run(pytester, '''
from sqlalchemy import select
from greentechhub_core.sqlalchemy import Database
from conftest import NOTES

db = Database("")  # no URL: anything that reaches the real engine fails


async def test_override(gth_database, gth_connection):
    with gth_database(db) as same:
        assert same is db
        async for session in db.session():
            await session.execute(NOTES.insert().values(text="via db"))
            rows = (await session.execute(select(NOTES.c.text))).scalars().all()
            assert rows == ["via db"] and session.bind is gth_connection
        assert (await db.ready()).status == "healthy"
    try:
        db.sessionmaker()
    except RuntimeError:
        pass
    else:
        raise AssertionError("the override wasn't reset")
''')
    result.assert_outcomes(passed=1)


def test_session_class_is_overridable(pytester: pytest.Pytester):
    result = _run(pytester, '''
import pytest
from sqlalchemy.ext.asyncio import AsyncSession


class MySession(AsyncSession):
    pass


@pytest.fixture(scope="session")
def gth_session_class():
    return MySession


async def test_class(gth_session):
    assert type(gth_session) is MySession
''')
    result.assert_outcomes(passed=1)


def test_a_reading_session_doesnt_undo_another_sessions_commit(pytester: pytest.Pytester):
    """The audit-log sequence: a route's session reads and stays open, a
    store's session commits a row, then the route's session closes."""
    result = _run(pytester, '''
from sqlalchemy import select
from sqlalchemy.orm import registry
from conftest import NOTES


class Note:
    pass


registry().map_imperatively(Note, NOTES)


async def _texts(session):
    return (await session.execute(select(NOTES.c.text))).scalars().all()


async def test_a_store_write_survives_the_route_closing(gth_sessionmaker):
    route = gth_sessionmaker()
    await _texts(route)                                  # SAVEPOINT opened, still open
    async with gth_sessionmaker() as store, store.begin():
        await store.execute(NOTES.insert().values(text="audit"))
    await route.close()
    async with gth_sessionmaker() as check:
        assert await _texts(check) == ["audit"]


async def test_uncommitted_core_writes_still_roll_back(gth_sessionmaker):
    writer = gth_sessionmaker()
    await writer.execute(NOTES.insert().values(text="forgot to commit"))
    await writer.close()
    async with gth_sessionmaker() as check:
        assert await _texts(check) == []


async def test_uncommitted_orm_writes_still_roll_back(gth_sessionmaker):
    writer = gth_sessionmaker()
    note = Note()
    note.text = "flushed"
    writer.add(note)
    await writer.flush()
    await writer.close()
    pending = gth_sessionmaker()
    other = Note()
    other.text = "pending"
    pending.add(other)                                   # never flushed: close mustn't flush it
    await pending.close()
    async with gth_sessionmaker() as check:
        assert await _texts(check) == []


async def test_text_statements_count_as_writes(gth_sessionmaker):
    from sqlalchemy import text

    writer = gth_sessionmaker()
    await writer.execute(text("INSERT INTO notes (text) VALUES ('raw')"))
    await writer.close()
    async with gth_sessionmaker() as check:
        assert await _texts(check) == []
''')
    result.assert_outcomes(passed=4)


def test_the_sync_session_class_keeps_its_own_methods(pytester: pytest.Pytester):
    result = _run(pytester, '''
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session


class MySyncSession(Session):
    def exec(self):
        return "mine"


class MySession(AsyncSession):
    sync_session_class = MySyncSession


@pytest.fixture(scope="session")
def gth_session_class():
    return MySession


async def test_sync_class(gth_session):
    assert isinstance(gth_session.sync_session, MySyncSession)
    assert gth_session.sync_session.exec() == "mine"
''')
    result.assert_outcomes(passed=1)
