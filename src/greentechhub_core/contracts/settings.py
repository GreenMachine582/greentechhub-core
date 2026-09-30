"""contracts.settings — SettingsStoreContract: shared conformance coverage
for any SettingsStore (this package's InMemorySettingsStore and
JsonFileSettingsStore, or a service's database-backed store) — see
docs/testing.md.

Needs one fixture:
    store: an empty SettingsStore — the tests write their own owners and
        keys and assert on what reads back.
"""

import asyncio

import pytest

from greentechhub_core.settings import SettingScope, SettingsStore

APP = SettingScope.APP
USER = SettingScope.USER


class SettingsStoreContract:
    """Inherit this class in a test module, defining `store` (empty) as a
    pytest fixture, to run the shared SettingsStore conformance suite
    against a concrete implementation.
    """

    def test_an_owner_with_nothing_stored_reads_empty(self, store: SettingsStore) -> None:
        assert store.get_many_sync(APP, None) == {}
        assert store.get_many_sync(USER, "unknown") == {}

    def test_values_read_back_with_their_types(self, store: SettingsStore) -> None:
        store.set_sync(APP, None, "a.flag", True)
        store.set_sync(APP, None, "a.count", 25)
        store.set_sync(APP, None, "a.text", "hello")
        values = store.get_many_sync(APP, None)
        assert values == {"a.flag": True, "a.count": 25, "a.text": "hello"}
        assert type(values["a.flag"]) is bool
        assert type(values["a.count"]) is int

    def test_set_overwrites(self, store: SettingsStore) -> None:
        store.set_sync(USER, "alice", "ui.theme", "dark")
        store.set_sync(USER, "alice", "ui.theme", "light")
        assert store.get_many_sync(USER, "alice") == {"ui.theme": "light"}

    def test_delete_removes_only_that_key(self, store: SettingsStore) -> None:
        store.set_sync(USER, "alice", "ui.theme", "dark")
        store.set_sync(USER, "alice", "ui.page_size", 50)
        store.delete_sync(USER, "alice", "ui.theme")
        assert store.get_many_sync(USER, "alice") == {"ui.page_size": 50}

    def test_deleting_a_missing_key_is_a_no_op(self, store: SettingsStore) -> None:
        store.delete_sync(APP, None, "missing")
        store.delete_sync(USER, "nobody", "missing")
        store.set_sync(USER, "alice", "ui.theme", "dark")
        store.delete_sync(USER, "alice", "missing")
        assert store.get_many_sync(USER, "alice") == {"ui.theme": "dark"}

    def test_owners_are_isolated(self, store: SettingsStore) -> None:
        store.set_sync(APP, None, "ui.theme", "light")
        store.set_sync(USER, "alice", "ui.theme", "dark")
        assert store.get_many_sync(APP, None) == {"ui.theme": "light"}
        assert store.get_many_sync(USER, "alice") == {"ui.theme": "dark"}
        assert store.get_many_sync(USER, "bob") == {}

    def test_get_many_returns_a_copy(self, store: SettingsStore) -> None:
        store.set_sync(APP, None, "ui.theme", "light")
        store.get_many_sync(APP, None)["ui.theme"] = "changed"
        assert store.get_many_sync(APP, None) == {"ui.theme": "light"}

    @pytest.mark.parametrize(("scope", "subject"), [(APP, "alice"), (USER, None), (USER, "")])
    def test_a_malformed_owner_raises(self, store: SettingsStore, scope, subject) -> None:
        with pytest.raises(ValueError):
            store.get_many_sync(scope, subject)
        with pytest.raises(ValueError):
            store.set_sync(scope, subject, "ui.theme", "dark")
        with pytest.raises(ValueError):
            store.delete_sync(scope, subject, "ui.theme")

    def test_async_and_sync_agree(self, store: SettingsStore) -> None:
        async def exercise() -> None:
            await store.set(USER, "dave", "ui.theme", "dark")
            await store.set(APP, None, "ui.page_size", 10)
            assert await store.get_many(USER, "dave") == store.get_many_sync(USER, "dave")
            assert await store.get_many(APP, None) == store.get_many_sync(APP, None)
            await store.delete(USER, "dave", "ui.theme")

        asyncio.run(exercise())
        assert store.get_many_sync(USER, "dave") == {}
