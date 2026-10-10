[← Back to README](README.md)

# ✅ TODO / Milestones

> Open work only: remove an item when it ships — its release note lands in CHANGELOG.md automatically (release-please). See [README.md](README.md) for context and [docs/](docs/) for the detailed design behind each item.
>
> Shipped work is recorded in [CHANGELOG.md](CHANGELOG.md) and on the [Releases page](https://github.com/GreenMachine582/greentechhub-core/releases) — this file only tracks what's still open. Sections are themes, not versions: release-please picks the version from the commits.

## 🗺️ Milestones

Cross-repo order (with greentechhub-fastapi and greentechhub-ui): consumers live (M3) → ui breaking release (M4) →
PyFinBot ready (M6) → v1.0. M1, M2 and M5 shipped; see the CHANGELOG.

### M6 PyFinBot ready — core's share
- [ ] `feat(security): API token store`, for greentechhub-fastapi's personal API tokens (its M6.3)
  - **Why:** PyFinBot's API is used from scripts with 24h login JWTs, which can't be revoked.
  - **Scope:**
    - an `ApiTokenStore` protocol (async with `_sync` twins), with `InMemoryApiTokenStore` and
      `SQLAlchemyApiTokenStore` over a `gth_api_tokens` table (`api_tokens_table(metadata)`);
    - a token is a random secret from `generate_token`, stored only as a hash. `create(owner, name, scopes,
      expires_at=None)` returns the plaintext once;
    - `verify(plaintext)` returns the token's owner and scopes (or None when unknown, revoked or expired) and
      records its last use. `list_for(owner)` and `revoke(id)` round it out;
    - scopes are permission strings; capping them by the owner's grants is the adapter's job;
    - an `ApiTokenStoreContract` in `greentechhub_core.contracts`.
  - **Done when:** both stores pass the contract, and fastapi can build its token views on it.
- [ ] `feat(background): held_lock`
  - **Why:** PyFinBot wraps `held` by hand for its syncs: a cached `FileLock` under `settings.lock_directory()`
    (`sync_guard`), and a hashed per-user lock name so it's safe as a filename (`email_sync_lock`).
  - **Scope:** `held_lock(settings, name, ttl=...)`, the same yield-True-or-False context manager as `held` on a
    `FileLock` cached per lock directory, plus `lock_name(*parts)` that hashes the parts into a filename-safe name.
  - **Done when:** PyFinBot's `sync_guard` and `email_sync_lock` are gone.
- [ ] `feat(config): retired settings`
  - **Why:** PyFinBot warns about env vars it no longer reads (`_warn_retired`), so a deployment notices a dropped
    setting instead of silently losing it.
  - **Scope:** a `retired` class attribute on `GTHBaseSettings` (name → what replaced it). Each one still set in the
    environment or `.env` logs one warning at startup, and nothing else changes.
  - **Done when:** PyFinBot's `_warn_retired` is gone.

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
- A `FileStore` protocol for attachments (local disk first, then S3/MinIO)
- A shared tags/labels model
- Webhooks — outbound (signed payloads, retries, a delivery log) and inbound (a signed payload becomes an
  `EventBus` event)
- More notification channels: ntfy or Gotify for self-hosted push, and Discord
- Prometheus metrics from the timing middleware and job runs

### v1.0 — Validated in production
- [ ] Both adapter packages consuming this package
- [ ] At least one FastAPI service consuming it in production
- [ ] GreenTechHub (Django) consuming it in production
- [ ] Contract-test suite ([docs/testing.md](docs/testing.md)) has caught at least one real drift

### Post-v1.0
- [ ] `gth` CLI ([docs/modules.md](docs/modules.md#cli-not-v1-worth-leaving-room-for)) — `gth new` (scaffold a
  FastAPI app with every `register_*`, the ui shell, SQLAlchemy stores, a Dockerfile and release-please) first,
  then `gth users create-admin`, `gth settings get/set`, `gth flags`, `gth jobs run`
