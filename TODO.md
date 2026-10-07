[← Back to README](README.md)

# ✅ TODO / Milestones

> Open work only: remove an item when it ships — its release note lands in CHANGELOG.md automatically (release-please). See [README.md](README.md) for context and [docs/](docs/) for the detailed design behind each item.
>
> Shipped work is recorded in [CHANGELOG.md](CHANGELOG.md) and on the [Releases page](https://github.com/GreenMachine582/greentechhub-core/releases) — this file only tracks what's still open. Sections are themes, not versions: release-please picks the version from the commits.

## 🗺️ Milestones

Cross-repo order (with greentechhub-fastapi and greentechhub-ui): Accounts (M1) → Notifications & email (M2) →
consumers live (M3) → ui breaking release (M4) → display & data (M5) → v1.0.

### Identity
- [ ] `AuthentikIdentityProvider`: validate `raw.headers["X-authentik-jwt"]` (when configured) against the issuer's
  JWKS. Worth doing once a service runs behind Authentik with JWT forwarding on

### Observability
- [ ] The full OTel `TracerProvider`/`MeterProvider`/exporter setup, once there's a collector to send to
  ([docs/modules.md](docs/modules.md#observability)). `get_resource_attributes` shipped ahead of it

### Leaner services — from the PyFinBot review (2026-10-07)
A review of PyFinBot and the adapters found framework-free code living in greentechhub-fastapi, and generic code
PyFinBot hand-rolls because nothing here offers it. One PR each, in this order. fastapi's TODO (M5) and PyFinBot's
`todo.md` hold the follow-ups that adopt them.

- [ ] C1. `feat(config)`: the adapter settings readers
  - **Why:** greentechhub-fastapi's `registration/_settings.py` (`setting_value`, `read_list_setting`,
    `read_str_setting`) and `registration/permissions.py` `read_role_map` are pure parsers of fields this package
    declares (`trusted_proxies`, `role_groups`, …). They hold the precedence rule (a service's SCREAMING_CASE
    attribute, then the lowercase field), and a Django adapter would have to copy them.
  - **Scope:**
    - `config`: `setting_value(settings, name)` plus list/str readers;
    - `permissions`: `parse_role_map(value, name)` (compact `"alice=admin|editor"` or JSON);
    - the same behaviour and errors as fastapi's today.
  - **Done when:** fastapi's copies become thin calls (its F6).
- [ ] C2. `feat(security)`: shared form checks
  - **Why:** the new-password rules and "Use at least N characters." / "The passwords don't match." are written out
    three times in fastapi (sign-up, reset, Settings › Password). `email_looks_valid` and "Enter an email address,
    like name@example.com." live in fastapi's `email.py`, and `email/message.py`'s `_check_address` is a weaker
    copy. PyFinBot's API password update checks nothing.
  - **Scope:**
    - `security.password_problems(new, confirm, *, min_length=8) -> list[str]`;
    - `email.email_looks_valid(address)`;
    - the messages as constants.
  - **Done when:** fastapi's three forms and PyFinBot's API use them.
- [ ] C3. `feat(config)`: service basics on `GTHBaseSettings`
  - **Why:** every service repeats these; PyFinBot's `core/settings.py` has them all.
  - **Scope:**
    - `environment` (`"development"`/`"production"`), with the dev CORS default (`*` when `cors_allowed_origins`
      is unset) and a production warning when it's empty;
    - `lock_dir` for `FileLock`;
    - an opt-in ephemeral `secret_key` (random per process, with a warning) for development.
  - **Done when:** PyFinBot's copies and its `pyfinbot.py` CORS block are gone.
- [ ] C4. `feat(sqlalchemy)`: session plumbing
  - **Why:** PyFinBot's `db/session.py` (about 65 lines) is generic: a lazy engine and sessionmaker, a
    `get_session` dependency body, a test override hook, the plain `session_factory` the SQLAlchemy stores here
    take, a `database_ready` health check, and an alembic `upgrade head` with absolute paths. Today
    `_sessions.py` is internal only.
  - **Scope:** a `Database(url, *, echo=False)` object with `session()`, `session_factory`, `override(factory)`,
    `ready()` and `migrate(alembic_ini, script_location)`. Framework-free; fastapi's dependency is a one-liner.
  - **Done when:** PyFinBot's `db/session.py` is a few lines over it.
- [ ] C5. `feat(background)`: a lock context manager
  - **Why:** PyFinBot's `market_sync.py` `sync_guard` wraps `FileLock` acquire/release in a context manager with a
    lazy singleton; the job-scheduler idea below wants the same.
  - **Scope:** `with held(lock, name, ttl):` over any `Lock` (`acquire(name, ttl)` / `release(name)`), raising a
    clear "already running" error when `acquire` returns False and releasing on exit.
  - **Done when:** PyFinBot's market, dividend and email syncs use it.
- [ ] C7. `greentechhub-testing` pytest plugin (promoted from Ideas)
  - **Why:** PyFinBot's `tests/conftest.py` has about 110 lines every service needs: SQLite savepoint
    engine/connection/session, a client with dependency and session-factory overrides, re-registering auth after
    `dependency_overrides.clear()`, `post_login` (the CSRF double-submit), `web_login` (the Secure cookie over
    http), and `hx_triggers`. greentechhub-fastapi's own tests repeat the HX-Trigger parsing.
  - **Scope:**
    - a separate package, or a `greentechhub-fastapi[testing]` extra for the HTTP fixtures;
    - plus `client_as(persona)` and fake stores.
  - **Done when:** PyFinBot's `conftest.py` is its own fixtures only.

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

### v1.0 — Validated in production
- [ ] Both adapter packages consuming this package
- [ ] At least one FastAPI service consuming it in production
- [ ] GreenTechHub (Django) consuming it in production
- [ ] Contract-test suite ([docs/testing.md](docs/testing.md)) has caught at least one real drift

### Post-v1.0
- [ ] `gth` CLI ([docs/modules.md](docs/modules.md#cli-not-v1-worth-leaving-room-for)) — `gth new` (scaffold a
  FastAPI app with every `register_*`, the ui shell, SQLAlchemy stores, a Dockerfile and release-please) first,
  then `gth users create-admin`, `gth settings get/set`, `gth flags`, `gth jobs run`
