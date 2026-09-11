"""health.checks.database — check_database: health check for a SQL database
reachable via a SQLAlchemy-shaped async engine, or any other async probe a
non-SQLAlchemy service wants to run instead.

No SQLAlchemy import: core has no SQLAlchemy dependency of its own, the
same "no third-party client dependency" posture check_external takes with
httpx. Health is checked duck-typed against SQLAlchemy AsyncEngine's shape
instead (engine.connect() -> an async context manager yielding a
connection with exec_driver_sql) — exec_driver_sql specifically, not
execute(): SQLAlchemy 2.x's Connection.execute() requires a text()-wrapped
Executable, which this module can't construct without importing
sqlalchemy, while exec_driver_sql accepts a raw SQL string directly and
has existed on both sync and async Connection since 1.4.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Protocol

from greentechhub_core.health.result import HealthResult, HealthStatus

Ping = Callable[[], Awaitable[None]]
"""A zero-arg async probe a non-SQLAlchemy service injects instead of an
engine — e.g. a driver-specific ping the service already has.
"""


class _AsyncConnection(Protocol):
    async def exec_driver_sql(self, statement: str) -> object: ...


class _ConnectContextManager(Protocol):
    async def __aenter__(self) -> _AsyncConnection: ...

    async def __aexit__(self, *exc_info: object) -> bool | None: ...


class _AsyncEngineLike(Protocol):
    def connect(self) -> _ConnectContextManager: ...


async def check_database(engine: "_AsyncEngineLike | Ping") -> HealthResult:
    """Check database connectivity via ``SELECT 1``.

    `engine` is duck-typed via ``hasattr(engine, "connect")``, not
    isinstance-checked (matching this Protocol's own structural-typing
    precedent elsewhere in this package — see IdentityProvider/
    FeatureFlagProvider):
      - Anything shaped like a SQLAlchemy AsyncEngine: opens a connection
        via ``engine.connect()`` and runs ``SELECT 1`` via
        ``exec_driver_sql`` — see this module's own docstring for why that
        method specifically.
      - Anything else is called directly as a zero-arg async probe
        (``await engine()``) — the ``Ping`` a non-SQLAlchemy service
        injects for its own driver. The parameter stays named ``engine`` to
        match the documented, common case; it still accepts either shape,
        so a service isn't forced onto SQLAlchemy just to get a health
        check.

    Never raises: any exception from either path becomes an ``unhealthy``
    HealthResult, matching ``run_checks``' own "a broken dependency
    shouldn't crash /health" posture — this check can also be run directly
    via ``run_checks`` without relying on that outer safety net.
    """
    start = time.perf_counter()
    try:
        if hasattr(engine, "connect"):
            async with engine.connect() as conn:  # type: ignore[union-attr]
                await conn.exec_driver_sql("SELECT 1")
        else:
            await engine()  # type: ignore[operator]
        status: HealthStatus = "healthy"
        detail = ""
    except Exception as exc:
        status = "unhealthy"
        # Some real exceptions stringify to "" (verified directly against
        # httpx.ConnectTimeout in check_external's own testing) — fall back
        # to the exception's type name so an unhealthy result is never left
        # with no detail at all, per HealthResult's own documented contract.
        detail = str(exc) or type(exc).__name__
    latency_ms = (time.perf_counter() - start) * 1000
    return HealthResult(status=status, detail=detail, latency_ms=latency_ms)
