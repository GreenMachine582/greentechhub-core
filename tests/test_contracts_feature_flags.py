import pytest

from greentechhub_core.contracts.feature_flags import FeatureFlagProviderContract
from greentechhub_core.feature_flags import EnvFileFeatureFlagProvider


class TestEnvFileFeatureFlagProviderContract(FeatureFlagProviderContract):
    @pytest.fixture
    def provider(self) -> EnvFileFeatureFlagProvider:
        return EnvFileFeatureFlagProvider()
