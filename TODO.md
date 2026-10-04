[← Back to README](README.md)

# ✅ TODO / Milestones

> Open work only: remove an item when it ships — its release note lands in CHANGELOG.md automatically (release-please). See [README.md](README.md) for context and [docs/](docs/) for the detailed design behind each item.
>
> Shipped work is recorded in [CHANGELOG.md](CHANGELOG.md) and on the [Releases page](https://github.com/GreenMachine582/greentechhub-core/releases) — this file only tracks what's still open. Sections are themes, not versions: release-please picks the version from the commits.

## 🗺️ Milestones

Cross-repo order (with greentechhub-fastapi and greentechhub-ui): Accounts (M1) → Notifications & email (M2) →
consumers live (M3) → ui breaking release (M4) → display & data (M5) → v1.0.

### Notifications & email (M2)
- [ ] Notifications — a notification model and a `NotificationStore` protocol (in-memory/JSON + SQLAlchemy, like
  settings and grants) with contract tests, for greentechhub-ui's notification centre; the `toast()` payload is
  the message shape, so a notice can be a toast now and a stored entry later
- [ ] Delivery preferences as user settings — in-app and/or email per notification category
- [ ] Expiring, single-use tokens for password reset and email verification, built on `generate_token` and storing
  only the hash
- [ ] Then: an audit/activity log (who did what, when) feeding greentechhub-ui's `gth_timeline` and, later, record
  history

### Identity
- [ ] `AuthentikIdentityProvider`: validate `raw.headers["X-authentik-jwt"]` (when configured) against the issuer's
  JWKS. Worth doing once a service runs behind Authentik with JWT forwarding on

### Observability
- [ ] The full OTel `TracerProvider`/`MeterProvider`/exporter setup, once there's a collector to send to
  ([docs/modules.md](docs/modules.md#observability)). `get_resource_attributes` shipped ahead of it

### Parked — until a consumer asks
- A currency setting: greentechhub-ui's `money` filter takes its symbol per call (default `$`); a shared
  `locale.currency` would let a user's or app's setting drive it

### Ideas — not scheduled
Core's share of ideas for more shared features; each pairs with a greentechhub-fastapi view and a greentechhub-ui
template (their TODOs list those halves).
- A settings-backed `FeatureFlagProvider` next to the env/file one, so flags can be toggled per app, user or group
- A job scheduler on `Lock`/`FileLock` that records each run (status, duration, output) — BottleBot scrapes,
  PyFinBot syncs
- Personal API tokens — a hashed token store with permission scopes and last-used time, on `generate_token`
- A `FileStore` protocol for attachments (local disk first, then S3/MinIO)
- A shared tags/labels model
- Webhooks — outbound (signed payloads, retries, a delivery log) and inbound (a signed payload becomes an
  `EventBus` event)
- More notification channels: ntfy or Gotify for self-hosted push, and Discord
- Prometheus metrics from the timing middleware and job runs
- A `greentechhub-testing` pytest plugin — `client_as(persona)`, fake identity/grant/settings stores, an htmx
  request helper

### v1.0 — Validated in production
- [ ] Both adapter packages consuming this package
- [ ] At least one FastAPI service consuming it in production
- [ ] GreenTechHub (Django) consuming it in production
- [ ] Contract-test suite ([docs/testing.md](docs/testing.md)) has caught at least one real drift

### Post-v1.0
- [ ] `gth` CLI ([docs/modules.md](docs/modules.md#cli-not-v1-worth-leaving-room-for)) — `gth new` (scaffold a
  FastAPI app with every `register_*`, the ui shell, SQLAlchemy stores, a Dockerfile and release-please) first,
  then `gth users create-admin`, `gth settings get/set`, `gth flags`, `gth jobs run`
