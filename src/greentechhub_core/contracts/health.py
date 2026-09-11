"""contracts.health — HealthCheckContract: shared conformance coverage for
any health check callable (this package's own check_disk, a future
check_database/check_redis/check_external, or an adapter's own check) — see
docs/testing.md.

A concrete subclass supplies one fixture:
    check: a zero-argument Callable[[], Awaitable[HealthResult]] (see
        health.run.Check) — e.g. `check_disk` bare, or
        `lambda: check_database(engine)` wrapped down to zero args for a
        check that needs arguments, matching docs/health.md's own
        convention.
"""

import asyncio

from greentechhub_core.health.result import HealthResult
from greentechhub_core.health.run import Check, run_checks


class HealthCheckContract:
    """Inherit this class in a test module, defining `check` as a pytest
    fixture, to run the shared health-check conformance suite against a
    concrete check.
    """

    def test_check_returns_a_health_result(self, check: Check) -> None:
        result = asyncio.run(check())
        assert isinstance(result, HealthResult)

    def test_latency_ms_is_non_negative(self, check: Check) -> None:
        result = asyncio.run(check())
        assert result.latency_ms >= 0

    def test_status_is_healthy_or_unhealthy(self, check: Check) -> None:
        result = asyncio.run(check())
        assert result.status in ("healthy", "unhealthy")

    def test_a_raising_check_is_caught_by_run_checks(self) -> None:
        async def _raising_check() -> HealthResult:
            raise RuntimeError("boom")

        results = asyncio.run(run_checks([_raising_check]))
        assert results[0].status == "unhealthy"
