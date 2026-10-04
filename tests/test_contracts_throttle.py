import pytest

from greentechhub_core.contracts.throttle import AttemptStoreContract
from greentechhub_core.security.throttle import InMemoryAttemptStore


class TestInMemoryAttemptStoreContract(AttemptStoreContract):
    @pytest.fixture
    def store(self) -> InMemoryAttemptStore:
        return InMemoryAttemptStore()
