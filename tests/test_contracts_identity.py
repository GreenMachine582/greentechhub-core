import pytest

from greentechhub_core.contracts.identity import IdentityProviderContract
from greentechhub_core.identity import (
    AuthentikIdentityProvider,
    DevelopmentIdentityProvider,
    RawAuthContext,
)


class TestDevelopmentIdentityProviderContract(IdentityProviderContract):
    @pytest.fixture
    def provider(self) -> DevelopmentIdentityProvider:
        return DevelopmentIdentityProvider(secret_key="test-secret-key")

    @pytest.fixture
    def valid_raw_context(self) -> RawAuthContext:
        return RawAuthContext(dev_mode=True)


class TestAuthentikIdentityProviderContract(IdentityProviderContract):
    @pytest.fixture
    def provider(self) -> AuthentikIdentityProvider:
        return AuthentikIdentityProvider()

    @pytest.fixture
    def valid_raw_context(self) -> RawAuthContext:
        return RawAuthContext(
            headers={
                "X-authentik-username": "jdoe",
                "X-authentik-groups": "admins|users",
                "X-authentik-email": "jdoe@example.com",
                "X-authentik-uid": "9f0e2372-driver-uid",
            }
        )
