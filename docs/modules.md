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

`background/locks.py` ships today — `Lock` (protocol) + `FileLock`, a single-host lock backed by a real OS-level advisory file lock (`fcntl.flock`/`msvcrt.locking`), so a scheduler-less service can still stop two replicas from running the same periodic job at once. No APScheduler dependency at all for this piece.

`background/scheduler.py`/`tasks.py` (an APScheduler wrapper with GreenTechHub conventions — structured logging per job run) are deliberately not built yet: zero consumers ask for a scheduler today, and APScheduler's own 4.x line has had a shifting pre-release API for an extended period, so wrapping either version now risks a rewrite before there's a real consumer to validate it against. Lands once a consumer needs ≥2 scheduled jobs, not on a fixed version. A distributed (multi-host) Redis-backed `Lock` is deferred the same way `events`'s Redis backend is — once Redis is deployed for some other reason.

## CLI (not v1, worth leaving room for)

```
gth init      # scaffold a new service's Settings/logging/health wiring
gth doctor    # check env vars, DB connectivity, required config against GTHBaseSettings
gth env       # print resolved config for the current service
gth health    # hit a running service's /health and pretty-print the result
```

Pure Python, depends only on `greentechhub-core` (plus `httpx` for `gth health`). Not scoped for v1 — noted here so the module boundaries elsewhere don't accidentally make it hard to add later (e.g. `config`/`health` are already CLI-friendly since they don't assume a request/response cycle).
