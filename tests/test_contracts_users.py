import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from greentechhub_core.contracts.users import UserStoreContract
from greentechhub_core.sqlalchemy import (
    SQLAlchemyUserStore,
    user_identities_table,
    users_table,
)
from greentechhub_core.users import InMemoryUserStore, UserExists


class TestInMemoryUserStoreContract(UserStoreContract):
    @pytest.fixture
    def store(self, clock) -> InMemoryUserStore:
        return InMemoryUserStore(clock=clock)


@pytest.fixture
def db(tmp_path):
    url = f"sqlite:///{tmp_path / 'users.db'}"
    metadata = sa.MetaData()
    identities = user_identities_table(metadata)
    users = metadata.tables["gth_users"]
    engine = sa.create_engine(url)
    metadata.create_all(engine)
    async_engine = create_async_engine(url.replace("sqlite", "sqlite+aiosqlite"),
                                       poolclass=NullPool)
    yield {
        "users": users,
        "identities": identities,
        "session_factory": sessionmaker(engine),
        "async_session_factory": async_sessionmaker(async_engine),
    }
    engine.dispose()


class TestSQLAlchemyUserStoreContract(UserStoreContract):
    @pytest.fixture
    def store(self, db, clock) -> SQLAlchemyUserStore:
        return SQLAlchemyUserStore(db["users"], db["identities"], clock=clock,
                                   session_factory=db["session_factory"],
                                   async_session_factory=db["async_session_factory"])


def test_tables_are_defined_once_per_metadata() -> None:
    metadata = sa.MetaData()
    assert users_table(metadata) is users_table(metadata)
    assert user_identities_table(metadata) is user_identities_table(metadata)


def test_a_concurrent_insert_is_reported_as_a_clash(db, monkeypatch) -> None:
    """When the pre-check misses a row a concurrent writer just added, the
    unique constraint still refuses it and the store says which field."""
    store = SQLAlchemyUserStore(db["users"], db["identities"],
                                session_factory=db["session_factory"])
    store.create_sync("alice")
    checks = []

    def miss_the_first_check(account, row):
        checks.append(row)
        if len(checks) > 1:
            SQLAlchemyUserStore._raise_clash(account, row)

    monkeypatch.setattr(store, "_raise_clash", miss_the_first_check)
    with pytest.raises(UserExists) as clash:
        store.create_sync("alice")
    assert clash.value.field == "username"
    assert [u.username for u in store.list_users_sync()] == ["alice"]
