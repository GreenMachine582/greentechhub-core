import pytest

from greentechhub_core.contracts.health import HealthCheckContract
from greentechhub_core.health import check_database, check_disk, check_external
from greentechhub_core.health.run import Check


class TestCheckDiskContract(HealthCheckContract):
    @pytest.fixture
    def check(self) -> Check:
        return check_disk


class _FakeConnection:
    async def exec_driver_sql(self, statement: str) -> None:
        return None


class _FakeConnectContextManager:
    async def __aenter__(self) -> _FakeConnection:
        return _FakeConnection()

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class _FakeEngine:
    def connect(self) -> _FakeConnectContextManager:
        return _FakeConnectContextManager()


class TestCheckDatabaseContract(HealthCheckContract):
    @pytest.fixture
    def check(self) -> Check:
        # Wrapped in a lambda: check_database takes an argument, so it
        # doesn't satisfy run_checks' zero-arg Check shape bare — matching
        # health.run's own documented convention for checks needing args.
        return lambda: check_database(_FakeEngine())


class _FakeResponse:
    status_code = 200


class _FakeHttpClient:
    async def get(self, url: str, *, timeout: float) -> _FakeResponse:
        return _FakeResponse()


class TestCheckExternalContract(HealthCheckContract):
    @pytest.fixture
    def check(self) -> Check:
        return lambda: check_external("https://example.test", client=_FakeHttpClient())
