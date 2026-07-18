"""run_checks — runs a list of zero-arg async health checks and collects their results.

Adapter packages need identical "run N checks, await them, collect results" logic
(see health_router(checks=[...]) and `await run_checks([check_database, check_disk])`),
so it lives here once rather than being duplicated per-adapter.

Checks that take arguments (e.g. check_database(engine)) don't satisfy the zero-arg
Callable shape run_checks expects — callers wrap them: `lambda: check_database(engine)`.
Checks whose parameters are all defaulted (e.g. check_disk) can be passed bare.
"""

import time
from asyncio import gather
from collections.abc import Awaitable, Callable, Sequence

from greentechhub_core.health.result import HealthResult

Check = Callable[[], Awaitable[HealthResult]]


async def run_checks(checks: Sequence[Check]) -> list[HealthResult]:
    """Run every check concurrently and return their results in the same order.

    A check that raises is converted into a HealthResult(status="unhealthy", ...)
    rather than propagating — the entire point of a health endpoint is surviving a
    dependency being down, so one broken/misbehaving check (e.g. check_database
    raising a connection error) must not take the whole /health response down with it.
    """
    return list(await gather(*(_run_one(check) for check in checks)))


async def _run_one(check: Check) -> HealthResult:
    start = time.perf_counter()
    try:
        return await check()
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return HealthResult(status="unhealthy", detail=str(exc), latency_ms=latency_ms)
