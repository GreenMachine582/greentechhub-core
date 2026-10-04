[← Back to README](../README.md)

# ⚙️ Settings and Role Resolution

> **Status: shipped.** Role resolution, setting definitions (with resolution and the built-ins), the settings stores,
> the `Settings` facade, secret settings, the landing-page, site-banner and self-signup factories and the SQLAlchemy storage tables have all shipped.
> The adapter work that builds on them is tracked in the fastapi and ui repos' TODOs.

Services need two kinds of runtime settings, alongside the env-driven `GTHBaseSettings`:

- **App settings.** Admins change these at runtime, e.g. a default page size or a maintenance banner.
- **User preferences.** Each person sets their own, e.g. theme, timezone or date format.

They also need a way to decide *who counts as an admin*. `permissions/` has the vocabulary (`Permission`, `Role`,
`has_permission`), and `RoleResolver` turns an `Identity` into a set of granted permissions.

## Principles

- **Opt-in.**
  - Nothing is auto-registered.
  - Built-in settings are an exported tuple that a service passes in itself.
  - The SQLAlchemy stores are only importable with the `[sqlalchemy]` extra, and `FernetCipher` with `[crypto]`.
  - Adapters wire things up only when the service calls their `register_*` function.
- **Core-first.**
  - Everything works from this package alone, with sync and async APIs, so a bot, CLI or Django service can use it
    without an adapter.
  - `greentechhub-fastapi` only wraps it in dependencies and routers. `greentechhub-ui` only renders it.
- **No Authentik dependency.**
  - Resolution works on any `Identity`, whether it comes from local auth, `DevelopmentIdentityProvider` or forward
    auth.
  - A bootstrap map (subject → roles) makes a first admin possible before any Authentik groups or grant rows exist.
- **Core holds no data.**
  - Core defines protocols, in-memory and JSON reference stores, and (behind the extra) SQLAlchemy stores.
  - Rows always live in the *service's* own database, migrated by its own Alembic.
  - Core ships no permission values or roles either. The service supplies its own, as
    [permissions.md](permissions.md) already requires.

## Role resolution (shipped)

| Piece | Shape |
|---|---|
| `PermissionResolver` | Protocol: `granted(identity) -> frozenset[Permission]`, with a `granted_sync` twin |
| `RoleResolver` | Union of `group_roles` (group → roles), `bootstrap` (subject → roles) and an optional `GrantStore` |
| `GrantStore` | Protocol: `roles_for(subject)`, `assign`, `revoke`, `list_assignments`; `InMemoryGrantStore` reference |

Usage and edge cases (fail-fast config, ignored stale grants, anonymous users) are in
[permissions.md](permissions.md#resolving-granted-permissions).

The union covers every way a person can be given roles:

- **Groups** answer "what does this person's directory group give them". With local auth the groups come from the
  service's own `LoginViews.authenticate()`.
- **Grants** are in-app assignments, keyed on `Identity.subject`.
- **Bootstrap** covers setup and recovery.

## Setting definitions and resolution (shipped)

| Piece | Shape |
|---|---|
| `Setting` | Frozen definition: `key`, `type` (bool/int/str/choice), `default`, `scope`, `label`, `help_text`, `choices`, `min`/`max`, `group`, `edit_permission`, `secret`; `validate(value)` and `coerce(raw)` |
| `SettingScope` | `APP` (one value per service) or `USER` (one per person; the app value is the admin-set default) |
| `SettingsRegistry` | Registration (duplicate keys fail fast), lookup, `validate`/`coerce` by key, `env_overrides`, `resolve`/`resolve_all` |
| `resolve` | Pure function over user, app and env mappings; no I/O |

```python
from greentechhub_core.settings import Setting, SettingScope, SettingsRegistry, SettingType
from greentechhub_core.settings.builtins import USER_PREFERENCES

BANNER = Setting(
    key="site.banner", type=SettingType.STR, default="", scope=SettingScope.APP,
    label="Maintenance banner", edit_permission="settings.manage",
)
registry = SettingsRegistry([*USER_PREFERENCES, BANNER])
env = registry.env_overrides()          # once, at startup; raises on a malformed value

registry.coerce("ui.page_size", "50")   # 50, from a form string
registry.resolve_all(user=user_values, app=app_values, env=env)
```

- **Definitions fail fast.** A malformed key (keys are lowercase dotted segments, e.g. `ui.page_size`), `choices` on a
  non-choice setting, `min`/`max` on a non-int one, `min > max`, or a default that doesn't validate raises
  `ValueError` at definition time.
- **`validate` never converts.** An int setting rejects `"5"` and `True`, a bool setting rejects `1`. `coerce` is the
  string path, for form fields and env vars. Bools accept `true/1/yes/on` and `false/0/no/off`.
- **`choices`** take a value → label mapping, bare values, or `(value, label)` pairs, and keep their order.
- **`edit_permission`** is a plain string, since `settings/` doesn't import `permissions/`. A `Permission` works as-is.
  The `Settings` facade (below) enforces it.

**Resolution order** for a USER setting is: user value, then app value (an admin-set default), then env override,
then the definition's default. An APP setting uses the same chain without the user step, and ignores user values.

- A stored value that no longer validates (say, a choice removed from code while its rows remain) is skipped, and
  resolution falls through to the next layer. This matches `RoleResolver` ignoring stale grant rows.
- **Env overrides** are read from `SETTING_` + the key uppercased, with `.` → `__`: `ui.page_size` comes from
  `SETTING_UI__PAGE_SIZE`. The prefix is overridable. `env_overrides()` raises naming the env var when a value
  doesn't coerce, or when one is set for a [secret setting](#secret-settings-shipped), so read it once at startup.

**Opt-in built-ins** live in `settings.builtins.USER_PREFERENCES`. Nothing registers them. A service passes the
tuple (or a subset) to its own registry. All are USER settings.

| Constant | Key | Type | Default | Values | Group |
|---|---|---|---|---|---|
| `THEME` | `ui.theme` | choice | `system` | `light`, `dark`, `system` | Appearance |
| `TIMEZONE` | `locale.timezone` | choice | `UTC` | IANA names from the host's tz database, plus `UTC` always | Locale |
| `DATE_FORMAT` | `locale.date_format` | choice | `iso` | `iso` (2026-01-31), `dmy` (31/01/2026), `mdy` (01/31/2026), `long` (31 Jan 2026) | Locale |
| `PAGE_SIZE` | `ui.page_size` | int | `25` | 5–200 | Tables |
| `DENSITY` | `ui.density` | choice | `comfortable` | `comfortable` (Comfortable), `compact` (Compact) | Appearance |
| `MOTION` | `ui.motion` | choice | `system` | `system` (Follow device), `reduce` (Reduce), `full` (Full) | Appearance |
| `SIDEBAR_DEFAULT` | `ui.sidebar_default` | choice | `expanded` | `expanded` (Expanded), `rail` (Icons only) | Appearance |
| `NUMBER_FORMAT` | `locale.number_format` | choice | `comma_dot` | `comma_dot` (1,234.56), `dot_comma` (1.234,56), `space_comma` (1 234,56) | Locale |
| `TIME_FORMAT` | `locale.time_format` | choice | `24h` | `24h` (13:45), `12h` (1:45 pm) | Locale |

- **The tuple is the set of shared keys greentechhub-ui honours, and it may grow.** A service passing the whole tuple
  shows every control, including ones ui doesn't apply yet. A service that wants a fixed set registers the individual
  constants instead.
- **`ui.sidebar_default`** seeds the sidebar's initial state from the server. As with the theme, localStorage stays as
  the in-session toggle and the fallback for anonymous users.
- **Honouring them is ui's job**, registered by greentechhub-ui's half of roadmap #12:
  - `data-gth-density` and `data-gth-motion` on `<html>`;
  - the number and time formats in the `number`, `money` and datetime filters;
  - the sidebar seed;
  - the landing-page redirect, which is fastapi's part.
- **Deliberately not built-ins:**
  - Notification preferences wait for ui's notification centre.
  - APP-scope settings such as a currency symbol are left to each service. The site banner is the exception: see
    [Site banner](#site-banner) below.
  - Per-table hidden columns stay in localStorage, because they're per page and per table rather than a shared key.

### Landing page (shipped)

| Factory | Key | Type | Default | Values | Group |
|---|---|---|---|---|---|
| `landing_page_setting(choices, *, default, label="Landing page", help_text=...)` | `ui.landing_page` (`LANDING_PAGE_KEY`) | choice | the caller's | the service's own pages, url → label | Navigation |

```python
from greentechhub_core.settings.builtins import USER_PREFERENCES, landing_page_setting

registry = SettingsRegistry([
    *USER_PREFERENCES,
    landing_page_setting({"/": "Dashboard", "/reports": "Reports"}, default="/"),
])
```

- It's a factory, not a constant, and isn't in `USER_PREFERENCES`, because its choices are the service's own pages.
  `choices` takes any form `Setting` accepts: a mapping, `(url, label)` pairs, or bare urls.
- `Setting`'s own validation rejects a `default` that isn't one of them, and empty choices. A stored page that's
  later removed from the choices falls back to the default, like any stale choice.
- Core only defines the setting. Acting on it (redirecting `/` or the post-login page to it) is the adapter's or
  service's job; `LANDING_PAGE_KEY` is the key to read.

### Site banner

| Factory | Keys | Types | Defaults | Values | Group |
|---|---|---|---|---|---|
| `site_banner_settings(*, edit_permission=None, group="Site")` | `site.banner` (`SITE_BANNER_KEY`), `site.banner_tone` (`SITE_BANNER_TONE_KEY`) | str, choice | `""` (no banner), `"warn"` | `SITE_BANNER_TONES`: info, warn, bad, good, neutral | Site |

```python
from greentechhub_core.settings.builtins import USER_PREFERENCES, site_banner_settings

registry = SettingsRegistry([
    *USER_PREFERENCES,
    *site_banner_settings(edit_permission="settings.manage"),
])
```

- An admin-set, site-wide message such as planned maintenance: APP scope, so one value for everyone.
- The tones are exactly greentechhub-ui's `gth_alert_banner` tones; a stored tone outside them falls back to `warn`.
- It's a factory, not a constant, because the permission that may edit it is the service's own.
- The split across the repos: core defines the settings; an adapter reads the resolved values and passes them to the
  template as greentechhub-ui's `site_banners` (greentechhub-fastapi's opt-in site banner); ui renders the strip
  above the navbar.

### Self-signup

| Factory | Key | Type | Default | Group |
|---|---|---|---|---|
| `self_signup_setting(*, default=True, edit_permission=None, group="Sign-up", label=..., help_text=...)` | `auth.self_signup` (`SELF_SIGNUP_KEY`) | bool | `True` (open) | Sign-up |

```python
from greentechhub_core.settings.builtins import USER_PREFERENCES, self_signup_setting

registry = SettingsRegistry([
    *USER_PREFERENCES,
    self_signup_setting(edit_permission="settings.manage"),   # default=False for invite-only
])
```

- Whether visitors may create their own account: APP scope, one switch for the site, open by default like
  greentechhub-fastapi's `RegisterViews`.
- A factory for the same reason as the site banner: the permission that may change it is the service's own.
- The split across the repos: core defines the setting; greentechhub-fastapi's `RegisterViews.is_open` reads it and
  answers 404 on the sign-up routes while it's off; greentechhub-ui's sign-in page shows "Create one" only when the
  view passes `register_url`.

## Settings stores and facade (shipped)

| Piece | Shape |
|---|---|
| `SettingsStore` | Protocol keyed by `(scope, subject \| None, key)`: `get_many(scope, subject)`, `set`, `delete`, each with a `_sync` twin |
| `InMemorySettingsStore` | Process-local reference store, for tests and single-process tools |
| `JsonFileSettingsStore` | One JSON file, `{"app": {...}, "user": {subject: {...}}}`, for services with no database |
| `Settings(registry, store)` | The facade: `effective`, `get`, `set_user`/`reset_user`, `set_app`/`reset_app`, each with a `_sync` twin |
| `SettingsStoreContract` | Conformance suite every store runs (`greentechhub_core.contracts.settings`) |

```python
from greentechhub_core.settings import JsonFileSettingsStore, Settings, SettingsRegistry
from greentechhub_core.settings.builtins import USER_PREFERENCES

settings = Settings(SettingsRegistry([*USER_PREFERENCES, BANNER]), JsonFileSettingsStore("data/settings.json"))

await settings.effective(identity)                       # every setting's value for this person
await settings.set_user(identity, "ui.theme", "dark")
granted = await resolver.granted(identity)               # RoleResolver, or any set of permission strings
await settings.set_app("site.banner", "Down at 5pm", granted=granted)
```

- **Owners.** An APP value's owner is `(APP, None)`; a USER value's is `(USER, identity.subject)`. A store raises
  `ValueError` for an APP owner with a subject or a USER owner without one.
- **Stores keep what they're given.** A store doesn't know the registry. `Settings` validates every write first,
  and resolution skips a stored value that no longer validates.
- **Env overrides** are read once when `Settings` is constructed (`registry.env_overrides()`, or pass `env=`), so a
  malformed one fails at startup.
- **Anonymous** (`identity=None`) reads skip the user layer. Anonymous writes raise `SettingPermissionError` with
  `permission=None`.
- **`set_user`** only takes USER settings (an APP key raises `ValueError`). `reset_user` drops the person's own value
  so they see the app value again.
- **`set_app`** takes any setting. For a USER setting it sets the default everyone without their own value sees.
  When the setting has an `edit_permission`, `granted` must contain it or `SettingPermissionError` (a
  `PermissionError`) is raised. A setting without one is left to the caller to guard, e.g. by only showing the admin
  form to admins. `granted` is required either way. `reset_app` drops the app value, with the same check.
- **Values are typed.** Writes go through `Setting.validate`, so a form string needs `registry.coerce` first.
- **`JsonFileSettingsStore`** reads the file on every call and replaces it atomically on write. It serialises writes
  within one process only, so run one writer per file. A missing file reads as empty; a malformed one raises
  `ValueError` and is never overwritten.
- `settings/` imports neither `permissions/` nor `identity/`: `identity` is anything with a `subject`, and `granted`
  is any collection of permission strings.

## Secret settings (shipped)

Some settings are credentials: an email app password, an API token. `Setting(..., secret=True)` keeps one encrypted at
rest and out of every read except one explicit call.

```python
from greentechhub_core.settings import SECRET_SET, Setting, Settings, SettingScope, SettingType
from greentechhub_core.settings.crypto import FernetCipher   # the [crypto] extra

APP_PASSWORD = Setting(
    key="email.app_password", type=SettingType.STR, default="", scope=SettingScope.USER,
    label="App password", group="Email sync", secret=True,
)
settings = Settings(registry, store, cipher=FernetCipher(config.settings_cipher_key))

await settings.set_user(identity, "email.app_password", "abcd efgh")      # encrypted before the store
await settings.get("email.app_password", identity)                        # SECRET_SET (None when unset)
await settings.get_secret("email.app_password", identity)                 # "abcd efgh", for server code only
await settings.reset_user(identity, "email.app_password")                 # removes it
```

| Piece | Shape |
|---|---|
| `Setting.secret` | `False` by default. Only a `str` setting with `default=""` can be secret, otherwise `ValueError` at definition time |
| `SecretCipher` | Protocol: `encrypt(plaintext: str) -> str`, `decrypt(token: str) -> str` |
| `FernetCipher(key)` | The shipped cipher, in `greentechhub_core.settings.crypto` behind the `[crypto]` extra (`cryptography`). `FernetCipher.generate_key()` makes a key |
| `SECRET_SET` | The marker reads return for a stored secret. Truthy, equal only to itself, and renders as `••••••••` |
| `SecretDecryptError` | A `ValueError`: the stored value doesn't decrypt with this cipher (the key changed, or the value was tampered with) |
| `Settings(..., cipher=)` | Required when the registry holds any secret setting |
| `get_secret(key, identity=None)` | The plaintext: the user value, else the app value, else `None`. Also `get_secret_sync` |

- **Fails fast.** A registry with a secret setting and no `cipher` raises `ValueError` naming the keys when `Settings`
  is built. A malformed Fernet key raises `ValueError` from `FernetCipher(key)`.
- **Writes** (`set_user`/`set_app`) validate the plaintext as a `str`, then store `cipher.encrypt(value)`. An empty
  value raises `ValueError`; use `reset_user`/`reset_app` to remove a secret. `edit_permission` applies as usual.
- **Reads.** `effective()` and `get()` give `SECRET_SET` when a value is stored (user or app layer) and `None` when
  not, so a template or form can say "saved" without ever holding the value. Test with `value is SECRET_SET`.
- **`get_secret`** raises `ValueError` for a setting that isn't secret, and `SecretDecryptError` when the stored value
  doesn't decrypt. `identity=None` skips the user layer, as for `get`.
- **No env overrides.** `read_env_overrides` raises `ValueError` naming the env var when one is set for a secret
  setting, and `Settings(env=...)` rejects a mapping that sets one. A secret only ever comes from an encrypted write.
- **Stores are unchanged.** They see an opaque string, so every `SettingsStore` (and `SettingsStoreContract`) works
  as-is: in memory, the JSON file and the `gth_settings` table all hold ciphertext.

**What it protects.** The value is encrypted at rest (a database dump, a backup, the JSON file) and never reaches a
template. The key is config, not a setting: keep it in an env var or a secret manager, outside the settings store, and
pass it to `FernetCipher` at startup. Anyone with the key and the store can decrypt.

**Changing the key** isn't handled: values written under the old key raise `SecretDecryptError` from `get_secret`
(reads still show `SECRET_SET`). Have people re-enter them, or decrypt and re-`set` each value with both ciphers in a
one-off script.

## Storage tables (shipped, `[sqlalchemy]` extra)

`pip install 'greentechhub-core[sqlalchemy]'` makes `greentechhub_core.sqlalchemy` importable. Without the extra,
importing it raises `ImportError` naming the extra; nothing else in core imports it.

| Piece | Shape |
|---|---|
| `settings_table(metadata)` | `gth_settings`: `scope`, `subject` (`""` for app rows), `key` (together the primary key), `value` (JSON), `updated_at` |
| `role_grants_table(metadata)` | `gth_role_grants`: `subject`, `role` (together the primary key), `granted_at` |
| `login_attempts_table(metadata)` | `gth_login_attempts`: `key` (the primary key), `failures`, `window_start`, `locked_until` (see [modules.md](modules.md#login-throttling)) |
| `notifications_table(metadata)` | `gth_notifications`: `id` (the primary key), `recipient`, `category`, `kind`, `title`, `message`, `icon`, `action_label`, `action_url`, `created_at`, `read_at`, indexed on (`recipient`, `read_at`) (see [modules.md](modules.md#notifications)) |
| `SQLAlchemySettingsStore(table, ...)` | A `SettingsStore` over `gth_settings` |
| `SQLAlchemyGrantStore(table, ...)` | A `GrantStore` over `gth_role_grants` |
| `SQLAlchemyAttemptStore(table, ...)` | An `AttemptStore` over `gth_login_attempts`, for `LoginThrottle` |
| `SQLAlchemyNotificationStore(table, ...)` | A `NotificationStore` over `gth_notifications` |

All four stores take `session_factory=` (a `sessionmaker`, for the `_sync` methods), `async_session_factory=` (an
`async_sessionmaker`, for the async ones), or both. Calling a method whose factory wasn't given raises
`RuntimeError`. Each call runs in its own transaction.

```python
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from greentechhub_core.permissions import RoleResolver
from greentechhub_core.settings import Settings, SettingsRegistry
from greentechhub_core.sqlalchemy import (
    SQLAlchemyGrantStore, SQLAlchemySettingsStore, role_grants_table, settings_table,
)

# models.py — on the metadata your Alembic env.py already uses
settings_rows = settings_table(Base.metadata)
grant_rows = role_grants_table(Base.metadata)

# startup
Session = async_sessionmaker(create_async_engine(DATABASE_URL))
grants = SQLAlchemyGrantStore(grant_rows, async_session_factory=Session)
resolver = RoleResolver(roles=ROLES, group_roles=GROUP_ROLES, bootstrap=BOOTSTRAP, grants=grants)
settings = Settings(registry, SQLAlchemySettingsStore(settings_rows, async_session_factory=Session))
```

**Alembic recipe.** The tables are ordinary `Table`s on your metadata, so migrations are the usual autogenerate:

1. Call `settings_table`/`role_grants_table`/`login_attempts_table`/`notifications_table` (the ones you use) in a module your `env.py` imports before it reads `target_metadata`
   (calling them again on the same metadata returns the existing table, so the app and `env.py` can both call them).
2. `alembic revision --autogenerate -m "gth settings and role grants"` detects them.
3. Review the revision and `alembic upgrade head`.

- `value` is SQLAlchemy's `JSON` type, so bools, ints and strings read back with their types on SQLite and
  PostgreSQL alike.
- `set` is an update, then an insert if no row matched, which works on every backend. A concurrent insert of the
  same row is retried once as an update. A concurrent `assign` of the same grant is treated as already assigned.
- An attempt store's `hit` raises the count in the database (`failures = failures + 1`), so simultaneous failures
  all count; a first failure whose insert loses a race is retried once as that increment. SQLite returns its
  datetimes without a zone; the store reads them back as UTC.
- Both stores pass `SettingsStoreContract` / `GrantStoreContract`, run against SQLite with sync and `aiosqlite`
  sessions.
