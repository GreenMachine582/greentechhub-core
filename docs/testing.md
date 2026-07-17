[← Back to README](../README.md)

# 🧪 Testing

- `pytest` unit tests per module — these are ordinary Python unit tests since nothing here touches a web framework, which is itself a testing-simplicity win from being [framework-independent](architecture.md).
- Contract tests for `IdentityProvider`, `FeatureFlagProvider`, and the [query](query.md)/[health](health.md) types — both adapter packages' test suites should import and run the same contract-test base classes against their concrete implementations, catching drift early.
- GitHub Actions: lint (ruff) + test, same pattern as the rest of the ecosystem.
