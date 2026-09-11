[← Back to README](../README.md)

# 🩺 Health Checks

```python
# greentechhub_core/health/checks/database.py
async def check_database(engine) -> HealthResult: ...

# greentechhub_core/health/checks/external.py
async def check_external(url, *, timeout=2.0, client=None) -> HealthResult: ...

# greentechhub_core/health/checks/disk.py
async def check_disk(path="/", *, min_free_ratio=0.1) -> HealthResult: ...
```

Checks are plain async functions returning a `HealthResult` (`status`, `detail`, `latency_ms`). Neither package defines a `/health` *route* — `greentechhub-fastapi` and `greentechhub-django` each expose one, both built by running the same list of checks. This is what makes every consuming service's `/health` report in a shape monitoring tooling can treat identically, regardless of which service it's watching.

None of this owns a database, cache, HTTP client, or container — `check_database`/`check_external` are duck-typed against an already-connected engine/injected client (no SQLAlchemy or `httpx` dependency in `greentechhub-core` itself; an adapter passes a real `SQLAlchemy AsyncEngine`/`httpx.AsyncClient`, or a plain zero-arg `async def ping()` for `check_database` when a service isn't on SQLAlchemy). Provisioning and connecting to the actual database/external endpoint/disk is entirely the consuming service's responsibility. `check_redis` is deferred until Redis is actually deployed for some other reason — the same trigger as `events`'s Redis backend and `background`'s distributed lock.

Every check degrades a raised exception into an `unhealthy` `HealthResult` rather than propagating (see `run_checks`) — including one whose `str()` is empty (e.g. `httpx.ConnectTimeout` genuinely stringifies to `""`), which falls back to the exception's type name so `detail` is never silently blank.
