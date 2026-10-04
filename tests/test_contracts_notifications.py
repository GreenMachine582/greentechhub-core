import pytest

from greentechhub_core.contracts.notifications import NotificationStoreContract
from greentechhub_core.notifications import InMemoryNotificationStore


class TestInMemoryNotificationStoreContract(NotificationStoreContract):
    @pytest.fixture
    def store(self) -> InMemoryNotificationStore:
        return InMemoryNotificationStore()
