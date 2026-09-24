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

Shipped versions and their notes: [CHANGELOG.md](CHANGELOG.md) and the [Releases page](https://github.com/GreenMachine582/greentechhub-core/releases) (both written by release-please from conventional commits). Open work: [TODO.md](TODO.md). Branches, PRs and how a release is cut: [CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 Licence

[MIT](LICENSE) © 2026 Matthew Johnson
