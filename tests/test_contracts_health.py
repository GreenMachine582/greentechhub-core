import pytest

from greentechhub_core.contracts.health import HealthCheckContract
from greentechhub_core.health import check_disk
from greentechhub_core.health.run import Check


class TestCheckDiskContract(HealthCheckContract):
    @pytest.fixture
    def check(self) -> Check:
        return check_disk
