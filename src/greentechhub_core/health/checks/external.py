"""health.checks.external — check_external: health check for a reachable
third-party HTTP dependency.

No httpx dependency in core, same reasoning as check_database's "no
SQLAlchemy import": the injected `client` is duck-typed via a Protocol
(structural, not isinstance-checked) instead. An adapter passes a real
`httpx.AsyncClient` (or anything else shaped like one); core never imports
it.
"""

import time
from typing import Protocol

from greentechhub_core.health.result import HealthResult, HealthStatus

_DEFAULT_TIMEOUT = 2.0


class _HttpResponse(Protocol):
    status_code: int


class _HttpClient(Protocol):
    async def get(self, url: str, *, timeout: float) -> _HttpResponse: ...


async def check_external(
    url: str, *, timeout: float = _DEFAULT_TIMEOUT, client: _HttpClient | None = None
) -> HealthResult:
    """Check that `url` responds with a non-error status.

    `client` has no usable default — core has no HTTP client dependency of
    its own to fall back on — so `client=None` (the caller forgot to inject
    one) raises `TypeError` immediately rather than producing a
    misleadingly-labeled "unhealthy" result: that's a caller-code mistake,
    not a fact about whether `url` is actually reachable, matching
    EnvFileFeatureFlagProvider's own "malformed configuration fails fast
    and loudly" precedent for a caller-authored setup error as opposed to
    genuinely untrusted/external input.

    A response is "healthy" for any status code below 400 — this checks
    whether `url` is actually working as expected, not merely whether the
    TCP port is open, so a 4xx/5xx (an expired credential, a broken
    downstream) counts as unhealthy same as a connection failure or
    timeout, both of which are caught below and never raise.
    """
    if client is None:
        raise TypeError(
            "check_external requires an injected client with an async "
            "get(url, timeout=...) method (e.g. httpx.AsyncClient) — core "
            "has no HTTP client dependency of its own"
        )

    start = time.perf_counter()
    try:
        response = await client.get(url, timeout=timeout)
        status: HealthStatus = "healthy" if response.status_code < 400 else "unhealthy"
        detail = f"HTTP {response.status_code}"
    except Exception as exc:
        status = "unhealthy"
        # Some real exceptions stringify to "" (e.g. httpx.ConnectTimeout,
        # verified directly against a real client) — a health check
        # reporting unhealthy with no detail at all defeats HealthResult's
        # own "should always populate it" contract, so fall back to the
        # exception's type name rather than an empty string.
        detail = str(exc) or type(exc).__name__
    latency_ms = (time.perf_counter() - start) * 1000
    return HealthResult(status=status, detail=detail, latency_ms=latency_ms)
