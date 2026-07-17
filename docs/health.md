[← Back to README](../README.md)

# 🩺 Health Checks

```python
# greentechhub_core/health/checks/database.py
async def check_database(engine) -> HealthResult: ...
```

Checks are plain async functions returning a `HealthResult` (`status`, `detail`, `latency_ms`). Neither package defines a `/health` *route* — `greentechhub-fastapi` and `greentechhub-django` each expose one, both built by running the same list of checks. This is what makes every consuming service's `/health` report in a shape monitoring tooling can treat identically, regardless of which service it's watching.

None of this owns a database, cache, or container — `check_database`/`check_redis` take an already-connected engine/client as an argument. Provisioning and connecting to the actual database/cache/disk is entirely the consuming service's responsibility; `greentechhub-core` has no persistent state or infrastructure of its own.
