"""sqlalchemy.database — Database: a service's async engine and sessions,
created lazily, with the pieces every service writes by hand: a session for
a framework dependency, the plain session factory this package's stores
take, a test override, a readiness check and an alembic upgrade.

    db = Database(settings.async_database_url)

    async def get_session():                 # the framework's dependency
        async for session in db.session():
            yield session

    store = SQLAlchemySettingsStore(SETTINGS_TABLE, async_session_factory=db.session_factory)
    register_health(app, checks=[db.ready])
    db.override(async_sessionmaker(bind=test_connection, ...))   # in tests

Nothing connects at import: the engine is built on first use, so a module
can create the Database before the URL is known to be usable.
"""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from greentechhub_core.health.checks.database import check_database
from greentechhub_core.health.result import HealthResult


class Database:
    """A lazily created async engine and sessionmaker for `url`.

    Args:
        url: the async database URL, e.g. "postgresql+asyncpg://…" or
            "sqlite+aiosqlite:///app.db". An empty one fails on first use,
            not at construction.
        echo: log SQL (SQLAlchemy's `echo`).
        session_class: the AsyncSession class sessions are made from, e.g.
            SQLModel's; session_factory() always gives a plain SQLAlchemy one.
        **engine_kwargs: passed to create_async_engine.
    """

    def __init__(
        self,
        url: str,
        *,
        echo: bool = False,
        session_class: type[AsyncSession] = AsyncSession,
        **engine_kwargs: Any,
    ) -> None:
        self._url = url
        self._echo = echo
        self._session_class = session_class
        self._engine_kwargs = engine_kwargs
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker | None = None
        self._override: async_sessionmaker | None = None

    @property
    def engine(self) -> AsyncEngine:
        """The engine, created on first use."""
        if self._engine is None:
            if not self._url:
                raise RuntimeError("Database: no database URL is configured")
            self._engine = create_async_engine(self._url, echo=self._echo, **self._engine_kwargs)
        return self._engine

    def sessionmaker(self) -> async_sessionmaker:
        """The sessionmaker sessions come from: a test override when one is
        set, else the engine's (expire_on_commit=False)."""
        if self._override is not None:
            return self._override
        if self._sessionmaker is None:
            self._sessionmaker = async_sessionmaker(
                bind=self.engine, class_=self._session_class, expire_on_commit=False
            )
        return self._sessionmaker

    def override(self, sessionmaker: async_sessionmaker | None) -> None:
        """Make sessions come from `sessionmaker` (tests bind one to their
        per-test connection), or go back to the engine's with None."""
        self._override = sessionmaker

    async def session(self) -> AsyncIterator[AsyncSession]:
        """One session, closed afterwards: the body of a framework's
        `get_session` dependency."""
        async with self.sessionmaker()() as session:
            yield session

    def session_factory(self) -> AsyncSession:
        """A new plain SQLAlchemy AsyncSession on the current sessionmaker's
        bind and options, looked up per call so an override applies: the
        zero-argument `async_session_factory` this package's stores take."""
        options = {k: v for k, v in self.sessionmaker().kw.items() if k != "class_"}
        return AsyncSession(**options)

    async def ready(self) -> HealthResult:
        """A readiness check: SELECT 1 through the current sessionmaker's
        bind (an engine, or a test override's connection)."""
        bind = self.sessionmaker().kw.get("bind")
        engine = bind if hasattr(bind, "connect") else getattr(bind, "engine", bind)
        return await check_database(engine)

    def migrate(
        self,
        alembic_ini: str | Path,
        script_location: str | Path,
        *,
        project_root: str | Path | None = None,
        revision: str = "head",
    ) -> None:
        """Run alembic `upgrade <revision>` (needs alembic installed).

        The paths are made absolute, so it works whatever the process's
        working directory. `project_root`, when given, goes on alembic's
        `prepend_sys_path`. env.py sees `config.attributes["configure_logger"]`
        as False, so it can skip alembic.ini's logging setup and keep the
        app's."""
        from alembic import command
        from alembic.config import Config

        config = Config(str(Path(alembic_ini).resolve()))
        config.set_main_option("script_location", str(Path(script_location).resolve()))
        if project_root is not None:
            # Split prepend_sys_path on the OS path separator, not alembic's
            # legacy spaces/commas/colons, which break a path with a space
            # (or a Windows drive letter).
            config.set_main_option("path_separator", "os")
            config.set_main_option("prepend_sys_path", str(Path(project_root).resolve()))
        config.attributes["configure_logger"] = False
        command.upgrade(config, revision)

    async def migrate_async(self, *args: Any, **kwargs: Any) -> None:
        """migrate() in a worker thread, for an app's startup."""
        await asyncio.to_thread(self.migrate, *args, **kwargs)

    async def dispose(self) -> None:
        """Close the engine's connections (e.g. at shutdown)."""
        if self._engine is not None:
            await self._engine.dispose()
