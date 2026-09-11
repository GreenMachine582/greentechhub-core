"""contracts.feature_flags — FeatureFlagProviderContract: shared conformance
coverage for any FeatureFlagProvider implementation (this package's own
EnvFileFeatureFlagProvider, or an adapter/service's own provider) — see
docs/testing.md.

A concrete subclass supplies one fixture:
    provider: a constructed FeatureFlagProvider whose is_enabled() has no
        pre-set opinion about _UNKNOWN_FLAG below — an adapter's own fixture
        must not seed that exact name.

Only garbage flag *names* are exercised here, not garbage configured
*values*: a provider deliberately raising on a malformed configured value
(e.g. EnvFileFeatureFlagProvider's env var `enbaled` typo case) is correct,
already-unit-tested behavior specific to that implementation, not something
a generic cross-implementation contract should assert either way.
"""

from greentechhub_core.feature_flags.provider import FeatureFlagProvider

_UNKNOWN_FLAG = "definitely-unknown-flag-xyz"
_GARBAGE_NAMES = ("", " ", "a b/c!", "🔥", "-", "FEATURE_ALREADY_PREFIXED")


class FeatureFlagProviderContract:
    """Inherit this class in a test module, defining `provider` as a pytest
    fixture, to run the shared FeatureFlagProvider conformance suite against
    a concrete implementation.
    """

    def test_unknown_flag_returns_false_by_default(self, provider: FeatureFlagProvider) -> None:
        assert provider.is_enabled(_UNKNOWN_FLAG) is False

    def test_unknown_flag_honours_explicit_default(self, provider: FeatureFlagProvider) -> None:
        assert provider.is_enabled(_UNKNOWN_FLAG, default=True) is True

    def test_is_enabled_never_raises_for_a_garbage_flag_name(
        self, provider: FeatureFlagProvider
    ) -> None:
        for name in _GARBAGE_NAMES:
            provider.is_enabled(name)
