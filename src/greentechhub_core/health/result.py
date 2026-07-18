"""HealthResult — the shape every check in greentechhub_core.health.checks returns.

Framework-independent by design: adapters each build their own /health route by
running the same list of checks (see run_checks in run.py) and rendering the same
HealthResult shape, so every consuming service's /health report looks identical to
monitoring tooling regardless of framework.
"""

from dataclasses import dataclass
from typing import Literal

HealthStatus = Literal["healthy", "unhealthy"]


@dataclass(frozen=True, slots=True, kw_only=True)
class HealthResult:
    """The result of running a single health check.

    Fields:
        status: "healthy" or "unhealthy" — deliberately binary, no "degraded" state.
        detail: a short human-readable explanation. Defaults to "" for the common
            "healthy, nothing more to say" case; checks reporting anything unhealthy
            (or healthy-but-noteworthy, e.g. disk free space) should always populate it.
        latency_ms: wall-clock time the check took, in milliseconds. No default —
            every check computes this itself via time.perf_counter(), so a caller
            forgetting to pass it is a bug worth a TypeError, not a silent 0.0.
    """

    status: HealthStatus
    detail: str = ""
    latency_ms: float
