import asyncio

import pytest

from greentechhub_core.health.checks import check_external


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _FakeClient:
    def __init__(self, *, status_code: int = 200, raises: Exception | None = None) -> None:
        self._status_code = status_code
        self._raises = raises
        self.calls: list[tuple[str, float]] = []

    async def get(self, url: str, *, timeout: float) -> _FakeResponse:
        self.calls.append((url, timeout))
        if self._raises is not None:
            raise self._raises
        return _FakeResponse(self._status_code)


def test_healthy_for_a_2xx_response():
    result = asyncio.run(check_external("https://example.test", client=_FakeClient()))
    assert result.status == "healthy"
    assert result.detail == "HTTP 200"


def test_unhealthy_for_a_4xx_response():
    result = asyncio.run(
        check_external("https://example.test", client=_FakeClient(status_code=404))
    )
    assert result.status == "unhealthy"


def test_unhealthy_for_a_5xx_response():
    result = asyncio.run(
        check_external("https://example.test", client=_FakeClient(status_code=503))
    )
    assert result.status == "unhealthy"


def test_unhealthy_when_the_client_raises():
    client = _FakeClient(raises=TimeoutError("timed out"))
    result = asyncio.run(check_external("https://example.test", client=client))
    assert result.status == "unhealthy"
    assert "timed out" in result.detail


def test_detail_falls_back_to_exception_type_name_when_str_is_empty():
    # Some real exceptions stringify to "" (httpx.ConnectTimeout does, per
    # this session's own live verification against a real httpx.AsyncClient).
    class _EmptyStrError(Exception):
        def __str__(self) -> str:
            return ""

    client = _FakeClient(raises=_EmptyStrError())
    result = asyncio.run(check_external("https://example.test", client=client))
    assert result.status == "unhealthy"
    assert result.detail == "_EmptyStrError"


def test_raises_type_error_when_client_is_not_supplied():
    with pytest.raises(TypeError):
        asyncio.run(check_external("https://example.test"))


def test_default_timeout_is_passed_through():
    client = _FakeClient()
    asyncio.run(check_external("https://example.test", client=client))
    assert client.calls == [("https://example.test", 2.0)]


def test_custom_timeout_is_passed_through():
    client = _FakeClient()
    asyncio.run(check_external("https://example.test", timeout=5.0, client=client))
    assert client.calls == [("https://example.test", 5.0)]


def test_latency_ms_is_a_non_negative_float():
    result = asyncio.run(check_external("https://example.test", client=_FakeClient()))
    assert isinstance(result.latency_ms, float)
    assert result.latency_ms >= 0.0
