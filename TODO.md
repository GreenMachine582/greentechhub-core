[← Back to README](README.md)

# ✅ TODO / Milestones

> Open work only: remove an item when it ships — its release note lands in CHANGELOG.md automatically (release-please). See [README.md](README.md) for context and [docs/](docs/) for the detailed design behind each item.
>
> Shipped work is recorded in [CHANGELOG.md](CHANGELOG.md) and on the [Releases page](https://github.com/GreenMachine582/greentechhub-core/releases) — this file only tracks what's still open.

## 🗺️ Milestones

### v0.5.1 — AuthentikIdentityProvider OIDC token path
- [ ] Validate `raw.headers["X-authentik-jwt"]` (when configured) against the issuer's JWKS

### v0.6 — Background, observability
- [ ] `observability` — the full OTel `TracerProvider`/`MeterProvider`/exporter setup, once there's a collector to send to ([docs/modules.md](docs/modules.md#observability)). `observability.resource`'s `get_resource_attributes` (`service.name`/`service.version`, no OTel import) has shipped ahead of the rest — the Loki/Alloy JSON logging pipeline wants the same fields today (`logging.setup.configure_logging`'s new `service`/`version` parameters), independent of OTel existing at all.

### Settings & permissions
Design: [docs/settings.md](docs/settings.md). Every item is opt-in, usable from this package alone, and works
without Authentik (local auth plus a bootstrap subject → role map). Each PR updates any doc it would otherwise
contradict. The order runs across repos: core #2–#4 here (#1, role resolution, has shipped), then fastapi #5,
ui #6–#8, fastapi #9, ui #10, fastapi #11, and the #12 scoping item.
- [ ] **#2 `feat(settings): setting definitions, registry and resolution`**
  - `SettingScope`, `Setting`, `SettingsRegistry` with validate/coerce.
  - Resolution order: user → app → env → default.
  - Opt-in `builtins.USER_PREFERENCES`: `ui.theme`, `locale.timezone`, `locale.date_format`, `ui.page_size`.
  - `settings/` doesn't import `permissions/`.
  - Docs: README module row, `docs/architecture.md`, `docs/modules.md`, and `docs/settings.md` from planned to
    shipped.
- [ ] **#3 `feat(settings): SettingsStore protocol, in-memory/JSON stores and Settings service`**
  - `SettingsStore` protocol with `InMemorySettingsStore` and `JsonFileSettingsStore`.
  - `Settings` facade: `effective`, `get`, `set_user`, and `set_app` with a permission check.
  - `SettingsStoreContract`.
- [ ] **#4 `feat(sqlalchemy): SQLAlchemy settings and grant stores`**
  - Optional `[sqlalchemy]` extra.
  - `gth_settings`/`gth_role_grants` tables on the service's `MetaData`, plus an Alembic recipe.
  - `SQLAlchemySettingsStore`/`SQLAlchemyGrantStore`, with the contracts run against them (aiosqlite).
  - Docs: reword "no SQLAlchemy dependency" to "no *required*" in `docs/health.md`, the
    `health/checks/database.py`/`external.py` docstrings and README.
- [ ] **#12 `docs: scope additional shared settings`** (with ui)
  - Decide on further opt-in built-ins: compact density for forms and tables, reduced motion, number/currency
    format, landing page, sidebar default, notification preferences.
  - The outcome is newly registered items, not code.

### v1.0 — Validated in production
- [ ] Both adapter packages consuming this package
- [ ] At least one FastAPI service consuming it in production
- [ ] GreenTechHub (Django) consuming it in production
- [ ] Contract-test suite ([docs/testing.md](docs/testing.md)) has caught at least one real drift

### Post-v1.0
- [ ] `gth` CLI ([docs/modules.md](docs/modules.md#cli-not-v1-worth-leaving-room-for))
