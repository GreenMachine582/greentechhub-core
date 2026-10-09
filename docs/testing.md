[← Back to README](../README.md)

# 🧪 Testing

- `pytest` unit tests per module — these are ordinary Python unit tests since nothing here touches a web framework, which is itself a testing-simplicity win from being [framework-independent](architecture.md).
- Contract tests for `IdentityProvider`, `FeatureFlagProvider`, `PermissionResolver`, `GrantStore`, `SettingsStore`, `AttemptStore`, `NotificationStore`, `TokenStore`, `AuditStore`, and the [query](query.md)/[health](health.md) types ship as `greentechhub_core.contracts` (the `contracts` optional dependency group) — both adapter packages' test suites import and subclass the same base classes against their concrete implementations, catching drift early:

  ```python
  from greentechhub_core.contracts.identity import IdentityProviderContract

  class TestMyProvider(IdentityProviderContract):
      @pytest.fixture
      def provider(self): return MyIdentityProvider(...)
      @pytest.fixture
      def valid_raw_context(self): return RawAuthContext(...)
  ```
- The SQLAlchemy stores run the same `SettingsStoreContract`, `GrantStoreContract`, `AttemptStoreContract`, `NotificationStoreContract`, `TokenStoreContract` and `AuditStoreContract` against a SQLite file through both a sync session and an `aiosqlite` async one; `.[dev]` installs SQLAlchemy and aiosqlite for that.
- GitHub Actions: lint (ruff) + test, same pattern as the rest of the ecosystem.

## Fixtures for a service's own tests

`greentechhub_core.testing.sqlalchemy` is a pytest plugin of per-test database fixtures (the `[testing]` extra:
pytest-asyncio, SQLAlchemy and aiosqlite). Nothing loads on install. A service opts in from its conftest and
says which tables to create:

```python
# tests/conftest.py
pytest_plugins = ["greentechhub_core.testing.sqlalchemy"]

@pytest.fixture(scope="session")
def gth_metadata():
    return SQLModel.metadata

@pytest.fixture(scope="session")
def gth_session_class():  # optional; defaults to SQLAlchemy's AsyncSession
    return sqlmodel.ext.asyncio.session.AsyncSession
```

- `gth_engine` is one SQLite file per test session, with the tables created.
- `gth_connection` wraps each test in a transaction that's rolled back afterwards. Sessions from
  `gth_sessionmaker` (and `gth_session`) join it with a SAVEPOINT, so tests never see each other's rows, even
  when the code under test commits.
- `gth_database(db)` is a context manager that points a `greentechhub_core.sqlalchemy.Database` at the test
  connection, and back again on exit. Use it so the app's `get_session`, its settings and grant stores, and
  its readiness check all use the test's transaction.

HTTP fixtures (a test client, signing in, `HX-Trigger` parsing) belong in greentechhub-fastapi.
