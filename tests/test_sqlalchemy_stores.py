import asyncio

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from greentechhub_core.contracts.notifications import NotificationStoreContract
from greentechhub_core.contracts.one_time import TokenStoreContract
from greentechhub_core.contracts.permissions import GrantStoreContract
from greentechhub_core.contracts.settings import SettingsStoreContract
from greentechhub_core.contracts.throttle import AttemptStoreContract
from greentechhub_core.identity.models import Identity
from greentechhub_core.permissions import Permission, Role, RoleResolver
from greentechhub_core.settings import Settings, SettingScope, SettingsRegistry
from greentechhub_core.settings.builtins import USER_PREFERENCES
from greentechhub_core.sqlalchemy import (
    SQLAlchemyAttemptStore,
    SQLAlchemyGrantStore,
    SQLAlchemyNotificationStore,
    SQLAlchemySettingsStore,
    SQLAlchemyTokenStore,
    login_attempts_table,
    notifications_table,
    one_time_tokens_table,
    role_grants_table,
    settings_table,
)


@pytest.fixture
def db(tmp_path):
    """A SQLite file with both tables, and a sync and an async session
    factory on it. The async engine uses NullPool because each
    asyncio.run() in the tests is a fresh event loop."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    metadata = sa.MetaData()
    tables = (settings_table(metadata), role_grants_table(metadata), login_attempts_table(metadata),
              notifications_table(metadata), one_time_tokens_table(metadata))
    engine = sa.create_engine(url)
    metadata.create_all(engine)
    async_engine = create_async_engine(
        url.replace("sqlite", "sqlite+aiosqlite"), poolclass=NullPool
    )
    yield {
        "settings": tables[0],
        "grants": tables[1],
        "attempts": tables[2],
        "notifications": tables[3],
        "tokens": tables[4],
        "session_factory": sessionmaker(engine),
        "async_session_factory": async_sessionmaker(async_engine),
    }
    engine.dispose()
    asyncio.run(async_engine.dispose())


def _factories(db) -> dict:
    return {k: db[k] for k in ("session_factory", "async_session_factory")}


class TestSQLAlchemySettingsStoreContract(SettingsStoreContract):
    @pytest.fixture
    def store(self, db) -> SQLAlchemySettingsStore:
        return SQLAlchemySettingsStore(db["settings"], **_factories(db))


class TestSQLAlchemyGrantStoreContract(GrantStoreContract):
    @pytest.fixture
    def store(self, db) -> SQLAlchemyGrantStore:
        return SQLAlchemyGrantStore(db["grants"], **_factories(db))


class TestSQLAlchemyNotificationStoreContract(NotificationStoreContract):
    @pytest.fixture
    def store(self, db) -> SQLAlchemyNotificationStore:
        return SQLAlchemyNotificationStore(db["notifications"], **_factories(db))


class TestSQLAlchemyTokenStoreContract(TokenStoreContract):
    @pytest.fixture
    def store(self, db) -> SQLAlchemyTokenStore:
        return SQLAlchemyTokenStore(db["tokens"], **_factories(db))


class TestSQLAlchemyAttemptStoreContract(AttemptStoreContract):
    @pytest.fixture
    def store(self, db) -> SQLAlchemyAttemptStore:
        return SQLAlchemyAttemptStore(db["attempts"], **_factories(db))


# tables


def test_tables_are_defined_once_per_metadata():
    metadata = sa.MetaData()
    assert settings_table(metadata) is settings_table(metadata)
    assert role_grants_table(metadata) is role_grants_table(metadata)
    assert set(metadata.tables) == {"gth_settings", "gth_role_grants"}


def test_app_rows_store_an_empty_subject(db):
    store = SQLAlchemySettingsStore(db["settings"], **_factories(db))
    store.set_sync(SettingScope.APP, None, "ui.theme", "dark")
    with db["session_factory"]() as session:
        row = session.execute(sa.select(db["settings"])).one()
    assert (row.scope, row.subject, row.key, row.value) == ("app", "", "ui.theme", "dark")
    assert row.updated_at is not None


# session factories


@pytest.mark.parametrize("cls", [SQLAlchemySettingsStore, SQLAlchemyGrantStore])
def test_needs_at_least_one_session_factory(cls):
    with pytest.raises(ValueError, match="session_factory"):
        cls(sa.Table("t", sa.MetaData()))


def test_a_missing_factory_raises_on_use(db):
    sync_only = SQLAlchemyGrantStore(db["grants"], session_factory=db["session_factory"])
    sync_only.assign_sync("alice", "admin")
    with pytest.raises(RuntimeError, match="async_session_factory"):
        asyncio.run(sync_only.roles_for("alice"))

    async_only = SQLAlchemyGrantStore(
        db["grants"], async_session_factory=db["async_session_factory"]
    )
    assert asyncio.run(async_only.roles_for("alice")) == frozenset({"admin"})
    with pytest.raises(RuntimeError, match="no session_factory"):
        async_only.roles_for_sync("alice")


# end to end


def test_settings_and_role_resolver_run_on_the_sqlalchemy_stores(db):
    manage = Permission("settings.manage")
    grants = SQLAlchemyGrantStore(db["grants"], **_factories(db))
    resolver = RoleResolver(roles=[Role(name="admin", permissions={manage})], grants=grants)
    store = SQLAlchemySettingsStore(db["settings"], **_factories(db))
    settings = Settings(SettingsRegistry(USER_PREFERENCES), store, env={})
    alice = Identity(subject="alice", username="alice", email=None, groups=[], claims={})

    async def exercise() -> None:
        await grants.assign("alice", "admin")
        assert await resolver.granted(alice) == frozenset({manage})
        await settings.set_app("ui.page_size", 50, granted=await resolver.granted(alice))
        await settings.set_user(alice, "ui.theme", "dark")
        effective = await settings.effective(alice)
        assert (effective["ui.theme"], effective["ui.page_size"]) == ("dark", 50)

    asyncio.run(exercise())
    assert settings.get_sync("ui.page_size") == 50


def test_secret_settings_are_ciphertext_in_the_table(db):
    from greentechhub_core.settings import SECRET_SET, Setting, SettingType
    from greentechhub_core.settings.crypto import FernetCipher

    password = Setting(
        key="email.app_password",
        type=SettingType.STR,
        default="",
        scope=SettingScope.USER,
        label="App password",
        secret=True,
    )
    store = SQLAlchemySettingsStore(db["settings"], **_factories(db))
    settings = Settings(
        SettingsRegistry([password]),
        store,
        env={},
        cipher=FernetCipher(FernetCipher.generate_key()),
    )
    alice = Identity(subject="alice", username="alice", email=None, groups=[], claims={})

    async def exercise() -> tuple:
        await settings.set_user(alice, "email.app_password", "hunter2")
        return await settings.get("email.app_password", alice), await settings.get_secret(
            "email.app_password", alice
        )

    assert asyncio.run(exercise()) == (SECRET_SET, "hunter2")
    with db["session_factory"]() as session:
        rows = [str(v) for v in session.execute(sa.select(db["settings"].c.value)).scalars()]
    assert rows and not any("hunter2" in v for v in rows)


def test_attempt_hit_retries_when_a_concurrent_insert_wins(db, monkeypatch):
    """Two first failures for one key at once: the loser's INSERT hits the
    primary key, so it retries and counts on the winner's row."""
    from datetime import UTC, datetime, timedelta

    store = SQLAlchemyAttemptStore(db["attempts"], **_factories(db))
    now, window = datetime(2026, 1, 1, tzinfo=UTC), timedelta(minutes=15)
    store.hit_sync("k", now, window)  # the "concurrent" winner, already committed

    real_record = SQLAlchemyAttemptStore._record
    misses = {"left": 0}  # how many reads still come back as "no row yet"

    def stale_read(row):
        if misses["left"] and row is not None:
            misses["left"] -= 1
            return None
        return real_record(row)

    monkeypatch.setattr(SQLAlchemyAttemptStore, "_record", staticmethod(stale_read))
    misses["left"] = 1
    assert store.hit_sync("k", now, window).failures == 2
    misses["left"] = 1
    assert asyncio.run(store.hit("k", now, window)).failures == 3
