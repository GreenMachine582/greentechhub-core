[← Back to README](../README.md)

# ⚙️ Settings and Role Resolution

> **Status: partly shipped.** Role resolution and setting definitions (with resolution and the built-ins) have
> shipped. Settings stores, the `Settings` facade and the storage tables are still planned, as the design the
> [TODO.md](../TODO.md#settings--permissions) items build towards. When an item ships, its section here moves from
> "planned" to "shipped".

Services need two kinds of runtime settings, alongside the env-driven `GTHBaseSettings`:

- **App settings.** Admins change these at runtime, e.g. a default page size or a maintenance banner.
- **User preferences.** Each person sets their own, e.g. theme, timezone or date format.

They also need a way to decide *who counts as an admin*. `permissions/` has the vocabulary (`Permission`, `Role`,
`has_permission`), and `RoleResolver` turns an `Identity` into a set of granted permissions.

## Principles

- **Opt-in.**
  - Nothing is auto-registered.
  - Built-in settings are an exported tuple that a service passes in itself.
  - The SQLAlchemy stores are only importable with the `[sqlalchemy]` extra.
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
| `Setting` | Frozen definition: `key`, `type` (bool/int/str/choice), `default`, `scope`, `label`, `help_text`, `choices`, `min`/`max`, `group`, `edit_permission`; `validate(value)` and `coerce(raw)` |
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
  doesn't coerce, so read it once at startup.

**Opt-in built-ins** live in `settings.builtins.USER_PREFERENCES`. Nothing registers them. A service passes the
tuple (or a subset) to its own registry.

| Key | Type | Default | Values |
|---|---|---|---|
| `ui.theme` | choice | `system` | `light`, `dark`, `system` |
| `locale.timezone` | choice | `UTC` | IANA names from the host's tz database, plus `UTC` always |
| `locale.date_format` | choice | `iso` | `iso` (2026-01-31), `dmy` (31/01/2026), `mdy` (01/31/2026), `long` (31 Jan 2026) |
| `ui.page_size` | int | `25` | 5–200 |

Further shared settings, such as compact density, are a separate scoping item.

## Settings stores and facade (planned)

- **`SettingsStore`**: a Protocol keyed by `(scope, subject | None, key)`, with `get_many`, `set` and `delete`.
  `InMemorySettingsStore` and `JsonFileSettingsStore` are the reference implementations.
- **`Settings(registry, store)`**: the facade, with `effective(identity)`, `get`, `set_user` and
  `set_app(..., granted=...)`. `set_app` checks `edit_permission`. It feeds the store's values and the env overrides
  into the registry's resolution above.

## Storage tables (planned, `[sqlalchemy]` extra)

`gth_settings` and `gth_role_grants` are defined on a `MetaData` the service passes in, so its own Alembic migrates
them. `SQLAlchemySettingsStore` and `SQLAlchemyGrantStore` both take a session factory. The contracts run against
every store.
