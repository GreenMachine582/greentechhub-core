import asyncio

from greentechhub_core.health.checks import check_disk


def test_healthy_when_min_free_ratio_is_zero(tmp_path):
    result = asyncio.run(check_disk(str(tmp_path), min_free_ratio=0.0))
    assert result.status == "healthy"


def test_unhealthy_when_min_free_ratio_is_impossible(tmp_path):
    # >100% free is unreachable on any real disk — deterministic without mocking
    # shutil.disk_usage or depending on actual free space on the test runner.
    result = asyncio.run(check_disk(str(tmp_path), min_free_ratio=1.1))
    assert result.status == "unhealthy"


def test_latency_ms_is_a_non_negative_float(tmp_path):
    result = asyncio.run(check_disk(str(tmp_path)))
    assert isinstance(result.latency_ms, float)
    assert result.latency_ms >= 0.0


def test_detail_reports_free_and_total_space(tmp_path):
    result = asyncio.run(check_disk(str(tmp_path)))
    assert "GiB" in result.detail
    assert "free" in result.detail


def test_default_path_is_usable_bare():
    # Proves check_disk needs no required args, so it can go directly into a
    # run_checks([...]) list without a wrapping lambda (per docs/health.md's Django
    # snippet: run_checks([check_database, check_disk])).
    result = asyncio.run(check_disk())
    assert result.status in ("healthy", "unhealthy")
