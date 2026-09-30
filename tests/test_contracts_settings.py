import pytest

from greentechhub_core.contracts.settings import SettingsStoreContract
from greentechhub_core.settings import InMemorySettingsStore, JsonFileSettingsStore


class TestInMemorySettingsStoreContract(SettingsStoreContract):
    @pytest.fixture
    def store(self) -> InMemorySettingsStore:
        return InMemorySettingsStore()


class TestJsonFileSettingsStoreContract(SettingsStoreContract):
    @pytest.fixture
    def store(self, tmp_path) -> JsonFileSettingsStore:
        return JsonFileSettingsStore(tmp_path / "settings.json")
