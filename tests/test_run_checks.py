import asyncio

from greentechhub_core.health import HealthResult, run_checks


def _ok(status="healthy", detail="fine"):
    async def _check():
        return HealthResult(status=status, detail=detail, latency_ms=1.0)

    return _check


def _boom(message="connection refused"):
    async def _check():
        raise RuntimeError(message)

    return _check


def test_empty_list_returns_empty_list():
    assert asyncio.run(run_checks([])) == []


def test_runs_multiple_checks_and_preserves_order():
    results = asyncio.run(run_checks([_ok(detail="first"), _ok(detail="second")]))
    assert [r.detail for r in results] == ["first", "second"]


def test_exception_in_a_check_becomes_unhealthy_result_not_a_crash():
    results = asyncio.run(run_checks([_boom("db down")]))
    assert results[0].status == "unhealthy"
    assert "db down" in results[0].detail


def test_one_broken_check_does_not_prevent_others_from_being_collected():
    results = asyncio.run(run_checks([_ok(), _boom(), _ok()]))
    assert [r.status for r in results] == ["healthy", "unhealthy", "healthy"]
