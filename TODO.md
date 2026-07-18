[← Back to README](README.md)

# ✅ TODO / Milestones

> This file is a living checklist — tick items off as they land instead of regenerating it. See [README.md](README.md) for context and [docs/](docs/) for the detailed design behind each item.

## 🗺️ Milestones

### v0.1 — Config, logging, health, proxy, version
Lowest-risk, highest immediate value, and already fully exercised by both planned adapter packages.

- [x] `config` — `GTHBaseSettings` ([docs/architecture.md](docs/architecture.md#package-layout))
- [x] `logging` — structured JSON setup ([docs/architecture.md](docs/architecture.md#package-layout))
- [x] `health` — check primitives only, no routes ([docs/health.md](docs/health.md))
- [x] `proxy` — `X-Forwarded-*` parsing/validation ([docs/modules.md](docs/modules.md#proxy))
- [ ] `version` — installed package/service version reporting ([docs/architecture.md](docs/architecture.md#package-layout))

### v0.2 — Query, security, types
Unblocks pagination/filtering work in `greentechhub-fastapi` and eventually Django.

- [ ] `query` — `Filter`, `Operator`, `Sort`, `Page`, `PageRequest` ([docs/query.md](docs/query.md))
- [ ] `security` — passwords, tokens, redact ([docs/modules.md](docs/modules.md#security))
- [ ] `types` — `FlashMessage`, `Result`, etc. ([docs/architecture.md](docs/architecture.md#package-layout))

### v0.3 — Identity, permissions
- [ ] `identity` — `DevelopmentIdentityProvider` first ([docs/identity.md](docs/identity.md))
- [ ] `permissions` — catalogue + `has_permission` primitives ([docs/permissions.md](docs/permissions.md))

### v0.4 — Events, feature flags
- [ ] `events` — `publish`/`subscribe`, log-backed ([docs/events.md](docs/events.md))
- [ ] `feature_flags` — env/file-backed `FeatureFlagProvider` ([docs/modules.md](docs/modules.md#feature-flags))

### v0.5 — Authentik-backed identity
- [ ] `identity`'s `AuthentikIdentityProvider`, once an Authentik instance actually exists to test against ([docs/identity.md](docs/identity.md))

### v0.6 — Background, observability
- [ ] `background` — scheduler/task/lock primitives ([docs/modules.md](docs/modules.md#background-tasks))
- [ ] `observability` — once there's an OTel collector to send to ([docs/modules.md](docs/modules.md#observability))

### v1.0 — Validated in production
- [ ] Both adapter packages consuming this package
- [ ] At least one FastAPI service consuming it in production
- [ ] GreenTechHub (Django) consuming it in production
- [ ] Contract-test suite ([docs/testing.md](docs/testing.md)) has caught at least one real drift

### Post-v1.0
- [ ] `gth` CLI ([docs/modules.md](docs/modules.md#cli-not-v1-worth-leaving-room-for))

## 🔄 Migration Tracking

Per-consumer adoption progress. Neither service depends on `greentechhub-core` directly; both go through their framework's adapter package.

### PyFinBot (via `greentechhub-fastapi`)
- [ ] Consuming `config`/`logging`/`health`
- [ ] Consuming `identity`/`permissions`

### BottleBot (via `greentechhub-fastapi`)
- [ ] Consuming `config`/`logging`/`health`
- [ ] Consuming `identity`/`permissions`

### Market Watch (planned, via `greentechhub-fastapi`)
- [ ] Not started — service doesn't exist yet

### GreenTechHub (via `greentechhub-django`)
- [ ] Consuming `config`/`logging`/`health`
- [ ] Consuming `identity`/`permissions`
