"""sqlalchemy.Database: a lazily created engine and sessionmaker, a
session for a framework dependency, the stores' session factory, a test
override, a readiness check and an alembic upgrade."""

import asyncio
import sqlite3
import textwrap

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from greentechhub_core.sqlalchemy import Database


def _url(tmp_path, name="app.db"):
    return f"sqlite+aiosqlite:///{tmp_path / name}"


def test_nothing_is_created_until_first_use(tmp_path):
    db = Database(_url(tmp_path))
    assert db._engine is None
    assert db.engine is db.engine  # created once, on first use
    asyncio.run(db.dispose())


def test_an_empty_url_fails_on_first_use_not_construction():
    db = Database("")
    with pytest.raises(RuntimeError, match="no database URL"):
        db.sessionmaker()


def test_session_yields_a_working_session(tmp_path):
    db = Database(_url(tmp_path))

    async def run():
        async for session in db.session():
            assert (await session.execute(text("select 1"))).scalar() == 1
        await db.dispose()

    asyncio.run(run())


def test_session_factory_is_a_plain_session_on_the_same_bind(tmp_path):
    class MySession(AsyncSession):
        pass

    db = Database(_url(tmp_path), session_class=MySession)

    async def run():
        async for session in db.session():
            assert type(session) is MySession
        plain = db.session_factory()
        assert type(plain) is AsyncSession and plain.bind is db.engine
        await plain.close()
        await db.dispose()

    asyncio.run(run())


def test_override_wins_and_resets(tmp_path):
    db = Database(_url(tmp_path, "real.db"))
    other = Database(_url(tmp_path, "other.db"))
    maker = async_sessionmaker(bind=other.engine, expire_on_commit=False)

    async def run():
        db.override(maker)
        assert db.sessionmaker() is maker
        assert db.session_factory().bind is other.engine
        db.override(None)
        assert db.session_factory().bind is db.engine
        await db.dispose()
        await other.dispose()

    asyncio.run(run())


def test_ready_passes_and_fails(tmp_path):
    good = Database(_url(tmp_path))
    bad = Database(f"sqlite+aiosqlite:///{tmp_path / 'missing' / 'nowhere.db'}")

    async def run():
        ok = await good.ready()
        down = await bad.ready()
        await good.dispose()
        await bad.dispose()
        return ok, down

    ok, down = asyncio.run(run())
    assert ok.status == "healthy"
    assert down.status == "unhealthy"


def test_ready_follows_a_connection_bound_override(tmp_path):
    db = Database(_url(tmp_path))

    async def run():
        async with db.engine.connect() as connection:
            db.override(async_sessionmaker(bind=connection, expire_on_commit=False))
            result = await db.ready()
        await db.dispose()
        return result

    assert asyncio.run(run()).status == "healthy"


def test_migrate_upgrades_to_head_from_any_working_directory(tmp_path, monkeypatch):
    pytest.importorskip("alembic")
    project = tmp_path / "project"
    versions = project / "migrations" / "versions"
    versions.mkdir(parents=True)
    db_path = tmp_path / "migrated.db"
    (project / "alembic.ini").write_text(textwrap.dedent(f"""\
        [alembic]
        script_location = migrations
        sqlalchemy.url = sqlite:///{db_path.as_posix()}
        """))
    (project / "migrations" / "env.py").write_text(textwrap.dedent("""\
        from alembic import context
        from sqlalchemy import engine_from_config, pool

        config = context.config
        assert config.attributes.get("configure_logger") is False
        engine = engine_from_config(config.get_section(config.config_ini_section),
                                    prefix="sqlalchemy.", poolclass=pool.NullPool)
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=None)
            with context.begin_transaction():
                context.run_migrations()
        """))
    (project / "migrations" / "script.py.mako").write_text("")
    (versions / "0001_widgets.py").write_text(textwrap.dedent("""\
        from alembic import op
        import sqlalchemy as sa

        revision = "0001"
        down_revision = None
        branch_labels = None
        depends_on = None

        def upgrade():
            op.create_table("widgets", sa.Column("id", sa.Integer, primary_key=True))

        def downgrade():
            op.drop_table("widgets")
        """))

    monkeypatch.chdir(tmp_path)  # not the project directory
    db = Database(_url(tmp_path, "unused.db"))
    asyncio.run(db.migrate_async(project / "alembic.ini", project / "migrations",
                                 project_root=project))

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("select name from sqlite_master where type='table'")
        tables = {row[0] for row in rows}
    assert "widgets" in tables
