[← Back to README](README.md)

# ✅ TODO / Milestones

> Open work only: remove an item when it ships — its release note lands in CHANGELOG.md automatically (release-please). See [README.md](README.md) for context and [docs/](docs/) for the detailed design behind each item.
>
> Shipped work is recorded in [CHANGELOG.md](CHANGELOG.md) and on the [Releases page](https://github.com/GreenMachine582/greentechhub-core/releases) — this file only tracks what's still open. Sections are themes, not versions: release-please picks the version from the commits.

## 🗺️ Milestones

### Identity
- [ ] `AuthentikIdentityProvider`: validate `raw.headers["X-authentik-jwt"]` (when configured) against the issuer's
  JWKS. Worth doing once a service runs behind Authentik with JWT forwarding on

### Observability
- [ ] The full OTel `TracerProvider`/`MeterProvider`/exporter setup, once there's a collector to send to
  ([docs/modules.md](docs/modules.md#observability)). `get_resource_attributes` shipped ahead of it

### Parked — until a consumer asks
- Notifications: a notification model, store and delivery preferences, for greentechhub-ui's planned notification
  centre (the `toast()` payload is the message shape)
- An audit/activity log (who did what, when) for greentechhub-ui's planned `gth_timeline`
- A currency setting: greentechhub-ui's `money` filter takes its symbol per call (default `$`); a shared
  `locale.currency` would let a user's or app's setting drive it

### v1.0 — Validated in production
- [ ] Both adapter packages consuming this package
- [ ] At least one FastAPI service consuming it in production
- [ ] GreenTechHub (Django) consuming it in production
- [ ] Contract-test suite ([docs/testing.md](docs/testing.md)) has caught at least one real drift

### Post-v1.0
- [ ] `gth` CLI ([docs/modules.md](docs/modules.md#cli-not-v1-worth-leaving-room-for))
