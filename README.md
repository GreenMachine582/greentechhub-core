# 🧱 greentechhub-core

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Tests](https://github.com/GreenMachine582/greentechhub-core/actions/workflows/ci.yml/badge.svg)](https://github.com/GreenMachine582/greentechhub-core/actions/workflows/ci.yml)
[![Status: Hold](https://img.shields.io/badge/Status-Hold-orange.svg)](TODO.md)
[![Python](https://img.shields.io/badge/Python-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Pydantic](https://img.shields.io/badge/Pydantic-E92063.svg?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![pytest](https://img.shields.io/badge/pytest-0A9EDC.svg?logo=pytest&logoColor=white)](https://docs.pytest.org/)

## 🎯 Objective

The framework-independent foundation every GreenTechHub-ecosystem service — FastAPI or Django, web app or CLI/worker — builds on: configuration, logging, identity and permission contracts, health-check logic, query/pagination/filtering contracts, an event bus abstraction, feature flags, observability setup, and shared security primitives. It contains no `import fastapi` or `import django` anywhere, and no database, cache, or deployment setup of its own — it's an installable library, not a service.

## 🧩 Scope

| Module | Responsibility                                                                                                             | Doc |
|---|----------------------------------------------------------------------------------------------------------------------------|---|
| `config` | `pydantic-settings` base class (`GTHBaseSettings`) every service's `Settings` extends                                      | [docs/architecture.md](docs/architecture.md) |
| `logging` | Structured (JSON) logging setup, request-ID-aware formatters, shaped for the homelab's Loki/Alloy pipeline                 | [docs/architecture.md](docs/architecture.md) |
| `identity` | Framework-independent identity model — the centrepiece of this package                                                     | [docs/identity.md](docs/identity.md) |
| `permissions` | Permission-check primitives and typed permission-catalogue helpers                                                         | [docs/permissions.md](docs/permissions.md) |
| `events` | `publish()`/`subscribe()` + typed event definitions — logs events today, Redis pub/sub later                               | [docs/events.md](docs/events.md) |
| `feature_flags` | A `FeatureFlagProvider` interface; env/static-file-backed implementation to start                                          | [docs/modules.md](docs/modules.md#feature-flags) |
| `health` | Check primitives + a `HealthResult` type — `check_disk`/`check_database`/`check_external` ship today; `check_redis` lands when Redis is deployed for some other reason | [docs/health.md](docs/health.md) |
| `query` | Framework-independent `Filter`, `Operator`, `Sort`, `Page`, `PageRequest` types and the response envelope shape            | [docs/query.md](docs/query.md) |
| `observability` | `resource.py`'s `get_resource_attributes` (`service.name`/`service.version`, no OTel import) ships today; the full OTel `TracerProvider`/`MeterProvider`/exporter setup stays deferred until a collector exists | [docs/modules.md](docs/modules.md#observability) |
| `security` | Password hashing, constant-time comparisons, secret redaction for logs, CSRF token generation                              | [docs/modules.md](docs/modules.md#security) |
| `proxy` | Pure functions parsing/validating `X-Forwarded-*` headers against a trusted-IP allowlist                                   | [docs/modules.md](docs/modules.md#proxy) |
| `version` | Reports installed `greentechhub-*` package versions + service version, for `/health`/`/version` and deploy debugging       | [docs/architecture.md](docs/architecture.md#package-layout) |
| `background` | `locks.py` — `Lock`/`FileLock`, OS-advisory-lock-backed, ships today; `scheduler.py`/`tasks.py` deferred until a consumer needs ≥2 scheduled jobs | [docs/modules.md](docs/modules.md#background-tasks) |
| `types` / `utils` | Shared value types (`FlashMessage`, `Result`/error types) and small utilities with no other natural home                   | [docs/architecture.md](docs/architecture.md) |
| `contracts` | Reusable `pytest` base classes (`IdentityProviderContract`, `FeatureFlagProviderContract`, `HealthCheckContract`, `PageContract`) adapters subclass against their own implementations — the `contracts` extra | [docs/testing.md](docs/testing.md) |

## 📚 Docs

| Doc | Covers |
|---|---|
| [docs/identity.md](docs/identity.md) | 🪪 The framework-independent identity model (read this first) |
| [docs/architecture.md](docs/architecture.md) | 🏗️ Layered architecture, package layout |
| [docs/permissions.md](docs/permissions.md) | 🔑 Global roles vs. application permissions |
| [docs/events.md](docs/events.md) | 📡 `publish`/`subscribe` event bus abstraction |
| [docs/query.md](docs/query.md) | 🔍 `Filter`/`Page`/`PageRequest` contracts shared by both adapters |
| [docs/health.md](docs/health.md) | 🩺 Health check primitives and `HealthResult` |
| [docs/modules.md](docs/modules.md) | 🧩 Feature flags, observability, security, proxy, background, CLI |
| [docs/testing.md](docs/testing.md) | 🧪 Unit + contract testing strategy |

## 🗺️ Status & Roadmap

**On hold.** v0.1–v0.5 have shipped — `config`/`logging`/`health`/`proxy`/`version`, `query`/`security`/`types`, `identity`/`permissions`, `events`/`feature_flags`, and `contracts` are all implemented and tested. v0.5's `AuthentikIdentityProvider` is shipped for its forward-auth header path — that half needed no live instance, only Authentik's stable, documented header set; the OIDC token path (validating `X-authentik-jwt` against the issuer's JWKS) does need a live instance and is planned for v0.5.1. Part of v0.6 has landed ahead of the rest: `background.locks` (`Lock`/`FileLock`) and `observability.resource`'s `get_resource_attributes`, plus the `check_database`/`check_external` health checks that v0.1 originally dropped — none of it needed a scheduler, an OTel collector, or a live consumer to build. The remainder (a real scheduler, the full OTel `TracerProvider`/`MeterProvider` setup, `check_redis`) stays deferred on its own triggers. Further work beyond that is paused pending the `greentechhub-fastapi`/`greentechhub-django` adapter packages existing and consuming this library (needed for v0.6 validation and the v1.0 bar). The phased rollout (v0.1 → v1.0) and per-service migration tracking remain a living checklist in [TODO.md](TODO.md).

## 📄 Licence

[MIT](LICENSE) © 2026 Matthew Johnson
