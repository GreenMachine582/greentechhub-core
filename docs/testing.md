[← Back to README](../README.md)

# 🧪 Testing

- `pytest` unit tests per module — these are ordinary Python unit tests since nothing here touches a web framework, which is itself a testing-simplicity win from being [framework-independent](architecture.md).
- Contract tests for `IdentityProvider`, `FeatureFlagProvider`, and the [query](query.md)/[health](health.md) types ship as `greentechhub_core.contracts` (the `contracts` optional dependency group) — both adapter packages' test suites import and subclass the same base classes against their concrete implementations, catching drift early:

  ```python
  from greentechhub_core.contracts.identity import IdentityProviderContract

  class TestMyProvider(IdentityProviderContract):
      @pytest.fixture
      def provider(self): return MyIdentityProvider(...)
      @pytest.fixture
      def valid_raw_context(self): return RawAuthContext(...)
  ```
- GitHub Actions: lint (ruff) + test, same pattern as the rest of the ecosystem.
