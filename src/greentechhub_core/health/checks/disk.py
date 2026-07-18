"""check_disk — reports on free space for a given filesystem path.

Async for interface consistency with the other (future) checks in this package
(check_database, check_redis, check_external all need to be async since their
underlying I/O is), even though shutil.disk_usage() is itself a fast, synchronous
stat-like syscall — not slow blocking I/O worth offloading via asyncio.to_thread.
"""

import shutil
import time

from greentechhub_core.health.result import HealthResult, HealthStatus

_BYTES_PER_GIB = 1024**3


async def check_disk(path: str = "/", *, min_free_ratio: float = 0.1) -> HealthResult:
    """Check free space on the filesystem containing ``path``.

    ``path`` defaults to ``"/"`` (the filesystem root — resolves correctly on both
    POSIX and Windows, since shutil.disk_usage resolves a bare "/" against the
    current drive on Windows). A service checking a specific mount (e.g. a data
    volume) overrides it, e.g. ``lambda: check_disk("/data")`` when passed into
    run_checks (see run.py) — matching the fastapi adapter doc's
    ``lambda: check_database(engine)`` convention for checks needing arguments.

    Unhealthy when the fraction of free space drops below ``min_free_ratio``
    (default 10%).
    """
    start = time.perf_counter()
    usage = shutil.disk_usage(path)
    latency_ms = (time.perf_counter() - start) * 1000

    free_ratio = usage.free / usage.total if usage.total else 0.0
    status: HealthStatus = "healthy" if free_ratio >= min_free_ratio else "unhealthy"
    detail = (
        f"{usage.free / _BYTES_PER_GIB:.2f} GiB free of "
        f"{usage.total / _BYTES_PER_GIB:.2f} GiB "
        f"({free_ratio:.1%} free, minimum {min_free_ratio:.1%} required) at {path!r}"
    )

    return HealthResult(status=status, detail=detail, latency_ms=latency_ms)
