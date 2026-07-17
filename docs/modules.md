[← Back to README](../README.md)

# 🧩 Feature Flags, Observability, Security, Proxy, Background, CLI

The smaller modules that don't warrant their own doc yet — see [docs/identity.md](identity.md), [docs/permissions.md](permissions.md), [docs/events.md](events.md), [docs/query.md](query.md), and [docs/health.md](health.md) for the higher-detail ones.

## Feature flags

Same evolve-the-adapter shape as [identity](identity.md) — starts as env/static-file-backed (`FeatureFlagProvider` protocol), room for a real flag service later without call-site changes.

## Observability

Sets up the OpenTelemetry `TracerProvider`/`MeterProvider` and exporter config; framework auto-instrumentation libraries (e.g. `opentelemetry-instrumentation-fastapi`) are adapter-layer — they explicitly import `fastapi`/`django`.

## Security

`passwords.py` provides bcrypt hash/verify functions so every service uses one hashing scheme instead of each rolling its own; `tokens.py` generates CSRF/opaque tokens (binding them to a request/response is adapter-layer); `redact.py` scrubs secrets from log lines before they hit `logging`. Framework-independent primitives only.

## Proxy

Pure `X-Forwarded-*` parsing/validation against a trusted-proxy allowlist, framework-independent by design — header-dict-in, validated-client-info-out. Middleware wiring itself is adapter-layer.

## Background tasks

`background/scheduler.py`/`tasks.py`/`locks.py` wraps APScheduler with GreenTechHub conventions (structured logging per job run, a lock primitive to prevent overlapping runs across replicas). Framework-independent — a scheduler doesn't need FastAPI or Django running to tick.

## CLI (not v1, worth leaving room for)

```
gth init      # scaffold a new service's Settings/logging/health wiring
gth doctor    # check env vars, DB connectivity, required config against GTHBaseSettings
gth env       # print resolved config for the current service
gth health    # hit a running service's /health and pretty-print the result
```

Pure Python, depends only on `greentechhub-core` (plus `httpx` for `gth health`). Not scoped for v1 — noted here so the module boundaries elsewhere don't accidentally make it hard to add later (e.g. `config`/`health` are already CLI-friendly since they don't assume a request/response cycle).
