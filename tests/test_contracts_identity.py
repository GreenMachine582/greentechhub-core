import pytest

from greentechhub_core.contracts.identity import IdentityProviderContract
from greentechhub_core.identity import DevelopmentIdentityProvider, RawAuthContext


class TestDevelopmentIdentityProviderContract(IdentityProviderContract):
    @pytest.fixture
    def provider(self) -> DevelopmentIdentityProvider:
        return DevelopmentIdentityProvider(secret_key="test-secret-key")

    @pytest.fixture
    def valid_raw_context(self) -> RawAuthContext:
        return RawAuthContext(dev_mode=True)
