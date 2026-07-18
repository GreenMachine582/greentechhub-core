import dataclasses

import pytest

from greentechhub_core.health import HealthResult


def test_construction_requires_keyword_args():
    HealthResult(status="healthy", latency_ms=1.0)
    with pytest.raises(TypeError):
        HealthResult("healthy", "", 1.0)


def test_detail_defaults_to_empty_string():
    result = HealthResult(status="healthy", latency_ms=0.0)
    assert result.detail == ""


def test_is_frozen():
    result = HealthResult(status="healthy", latency_ms=1.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.status = "unhealthy"


def test_equality_is_value_based():
    a = HealthResult(status="healthy", detail="fine", latency_ms=1.0)
    b = HealthResult(status="healthy", detail="fine", latency_ms=1.0)
    assert a == b
