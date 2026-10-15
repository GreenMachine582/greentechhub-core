import pytest

from greentechhub_core.contracts.api_tokens import ApiTokenStoreContract
from greentechhub_core.security.api_tokens import InMemoryApiTokenStore


class TestInMemoryApiTokenStoreContract(ApiTokenStoreContract):
    @pytest.fixture
    def store(self, clock) -> InMemoryApiTokenStore:
        return InMemoryApiTokenStore(clock=clock)
