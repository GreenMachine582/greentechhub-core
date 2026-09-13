[← Back to README](README.md)

# ✅ TODO / Milestones

> This file is a living checklist — tick items off as they land instead of regenerating it. See [README.md](README.md) for context and [docs/](docs/) for the detailed design behind each item.
>
> A milestone isn't ticked off until its version tag (`git tag vX.Y.0`) actually exists — matching `pyproject.toml`.

## 🗺️ Milestones

### v0.1 — Config, logging, health, proxy, version
Lowest-risk, highest immediate value, and already fully exercised by both planned adapter packages.

- [x] `config` — `GTHBaseSettings` ([docs/architecture.md](docs/architecture.md#package-layout))
- [x] `logging` — structured JSON setup ([docs/architecture.md](docs/architecture.md#package-layout))
- [x] `health` — check primitives only, no routes ([docs/health.md](docs/health.md)). `check_database`/`check_external` were silently dropped from the original v0.1 shipment (only `check_disk` landed) — added now, duck-typed with no SQLAlchemy/`httpx` dependency in core. `check_redis` still deferred until Redis is deployed for some other reason.
- [x] `proxy` — `X-Forwarded-*` parsing/validation ([docs/modules.md](docs/modules.md#proxy))
- [x] `version` — installed package/service version reporting ([docs/architecture.md](docs/architecture.md#package-layout))

### v0.2 — Query, security, types
Unblocks pagination/filtering work in `greentechhub-fastapi` and eventually Django.

- [x] `query` — `Filter`, `Operator`, `Sort`, `Page`, `PageRequest` ([docs/query.md](docs/query.md))
- [x] `security` — passwords, tokens, redact ([docs/modules.md](docs/modules.md#security))
- [x] `types` — `FlashMessage`, `Result`, etc. ([docs/architecture.md](docs/architecture.md#package-layout))

### v0.3 — Identity, permissions
- [x] `identity` — `DevelopmentIdentityProvider` first ([docs/identity.md](docs/identity.md))
- [x] `permissions` — catalogue + `has_permission` primitives ([docs/permissions.md](docs/permissions.md))

### v0.4 — Events, feature flags
- [x] `events` — `publish`/`subscribe`, log-backed ([docs/events.md](docs/events.md))
- [x] `feature_flags` — env/file-backed `FeatureFlagProvider` ([docs/modules.md](docs/modules.md#feature-flags))

### v0.4.1 — Contract test base classes
Unblocks adapter packages, which had no reusable base classes to test their own `IdentityProvider`/`FeatureFlagProvider`/health/query implementations against.

- [x] `contracts.identity` — `IdentityProviderContract` ([docs/testing.md](docs/testing.md))
- [x] `contracts.feature_flags` — `FeatureFlagProviderContract` ([docs/testing.md](docs/testing.md))
- [x] `contracts.health` — `HealthCheckContract` ([docs/testing.md](docs/testing.md))
- [x] `contracts.query` — `PageContract` ([docs/testing.md](docs/testing.md))

### v0.5 — Authentik-backed identity
- [x] `identity`'s `AuthentikIdentityProvider` — forward-auth header path only ([docs/identity.md](docs/identity.md)). Doesn't need a live instance: Authentik's forward-auth header set is stable and documented, and this class is "header-dict-in, Identity-out" like `proxy.trusted_proxy`. OIDC token validation needs the issuer's JWKS and is deferred — see v0.5.1.

### v0.5.1 — AuthentikIdentityProvider OIDC token path
`# planned` — gated on a real Authentik instance to fetch/validate against its JWKS, unlike the header path above.

- [ ] Validate `raw.headers["X-authentik-jwt"]` (when configured) against the issuer's JWKS

### v0.6 — Background, observability
- [x] `background.locks` — `Lock` protocol + `FileLock` (OS-advisory-lock-backed, single-host) ([docs/modules.md](docs/modules.md#background-tasks)). `scheduler`/`tasks` deferred until a consumer needs ≥2 scheduled jobs — zero consumers ask for a scheduler today, and APScheduler's own 4.x line has had a shifting pre-release API for years; wrapping either version now risks a rewrite before there's a consumer to validate against.
- [ ] `observability` — the full OTel `TracerProvider`/`MeterProvider`/exporter setup, once there's a collector to send to ([docs/modules.md](docs/modules.md#observability)). `observability.resource`'s `get_resource_attributes` (`service.name`/`service.version`, no OTel import) has shipped ahead of the rest — the Loki/Alloy JSON logging pipeline wants the same fields today (`logging.setup.configure_logging`'s new `service`/`version` parameters), independent of OTel existing at all.

### v1.0 — Validated in production
- [ ] Both adapter packages consuming this package
- [ ] At least one FastAPI service consuming it in production
- [ ] GreenTechHub (Django) consuming it in production
- [ ] Contract-test suite ([docs/testing.md](docs/testing.md)) has caught at least one real drift

### Post-v1.0
- [ ] `gth` CLI ([docs/modules.md](docs/modules.md#cli-not-v1-worth-leaving-room-for))

## 🔄 Migration Tracking

Per-consumer adoption tracking lives in each adapter's own `TODO.md`, not duplicated here — those have the
real, specific tasks; this repo's consumers never depend on it directly, only through an adapter:
- PyFinBot / BottleBot / Market Watch (via `greentechhub-fastapi`) —
  [greentechhub-fastapi/TODO.md](https://github.com/GreenMachine582/greentechhub-fastapi/blob/main/TODO.md#-migration-tracking)
- GreenTechHub (via `greentechhub-django`) —
  [greentechhub-django/TODO.md](https://github.com/GreenMachine582/greentechhub-django/blob/main/TODO.md#-migration-tracking)
