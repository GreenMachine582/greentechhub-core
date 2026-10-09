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
