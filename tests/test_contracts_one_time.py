import pytest

from greentechhub_core.contracts.one_time import TokenStoreContract
from greentechhub_core.security.one_time import InMemoryTokenStore


class TestInMemoryTokenStoreContract(TokenStoreContract):
    @pytest.fixture
    def store(self) -> InMemoryTokenStore:
        return InMemoryTokenStore()
