import pytest

from greentechhub_core.audit import InMemoryAuditStore
from greentechhub_core.contracts.audit import AuditStoreContract


class TestInMemoryAuditStoreContract(AuditStoreContract):
    @pytest.fixture
    def store(self) -> InMemoryAuditStore:
        return InMemoryAuditStore()
