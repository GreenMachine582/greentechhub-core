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
contradict. The core items (#1–#4: role resolution, setting definitions, the settings stores/facade and the
SQLAlchemy stores) and #13 (the density, motion, sidebar, number and time format built-ins) have shipped, and
core's half of the #12 scoping item is done. The order continues across repos: fastapi #5, ui #6–#8, fastapi #9,
ui #10, fastapi #11. #14 here has no dependencies and can land any time, but must land before ui's half of #12
(honouring the new keys).
- [ ] **#14 `feat(settings): landing_page_setting factory`**
  - `landing_page_setting(choices, *, default, label="Landing page")` returns a USER `Setting` keyed
    `ui.landing_page`, in the Navigation group.
  - Exported from `settings.builtins`, and not added to `USER_PREFERENCES`, because the choices are the service's own
    pages.
  - Tests: a valid default; a default outside the choices raises `ValueError`; mapping and pair forms of `choices`.
  - Docs: the `docs/settings.md` "Landing page (planned)" section moves to shipped.

#### Secret settings
Settings whose value is a credential (an email app password, an API token) can't be plain settings: stores keep JSON
as-is, `effective()` returns values to templates, and `SettingsViews` echoes a `str` back into the form. These items
add an opt-in **secret** kind across the three packages. Order across repos: core #18 → ui #19 → fastapi #20, then
releases core v0.8.0, ui v0.13.0 and fastapi v0.10.0 (fastapi pins core v0.8.0 first). The first consumer is
PyFinBot's per-user email account for Commsec sync (its app password), registered in PyFinBot's `todo.md`.
- [ ] **#18 `feat(settings): secret settings`**
  - `Setting(..., secret=True)`, allowed for `str` only (`ValueError` otherwise).
  - A `SecretCipher` protocol (`encrypt(str) -> str`, `decrypt(str) -> str`). `FernetCipher(key)` implements it
    behind a new optional `[crypto]` extra (`cryptography`); importing it without the extra raises an `ImportError`
    that names the extra.
  - `Settings(registry, store, cipher=None)`:
    - a registry holding a secret setting and no cipher fails fast at construction;
    - writes (`set_user`/`set_app`) encrypt before the store, so stores stay unaware;
    - `effective()` and `get()` never return the plaintext, only `SECRET_SET` or `None`;
    - `get_secret(key, identity=None)` (sync and async) returns the plaintext for server code;
    - `reset_user`/`reset_app` clear it, as usual.
  - Secrets are excluded from env overrides.
  - Tests: round-trip, the marker, a wrong key, a missing cipher, the ciphertext in the store, no env overrides.
    Contract: `SettingsStoreContract` is unchanged (the store sees opaque strings).
  - Docs: `docs/settings.md` "Secret settings" and the README row.

### v1.0 — Validated in production
- [ ] Both adapter packages consuming this package
- [ ] At least one FastAPI service consuming it in production
- [ ] GreenTechHub (Django) consuming it in production
- [ ] Contract-test suite ([docs/testing.md](docs/testing.md)) has caught at least one real drift

### Post-v1.0
- [ ] `gth` CLI ([docs/modules.md](docs/modules.md#cli-not-v1-worth-leaving-room-for))
