[← Back to README](../README.md)

# ⚙️ Settings and Role Resolution (planned)

> **Status: planned, not shipped.** This is the design the [TODO.md](../TODO.md#settings--permissions) items build
> towards. Nothing described here exists yet. When an item ships, its section here moves from "planned" to "shipped".

Services need two kinds of runtime settings, alongside the env-driven `GTHBaseSettings`:

- **App settings.** Admins change these at runtime, e.g. a default page size or a maintenance banner.
- **User preferences.** Each person sets their own, e.g. theme, timezone or date format.

They also need a way to decide *who counts as an admin*. `permissions/` already has the vocabulary (`Permission`,
`Role`, `has_permission`), but nothing turns an `Identity` into a set of granted permissions.

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

## Role resolution (planned)

| Piece | Shape |
|---|---|
| `PermissionResolver` | Protocol: `granted(identity) -> frozenset[Permission]`, sync and async |
| `GroupRoleResolver` | `Identity.groups` → the service's `Role`s via a `group_roles` mapping |
| `GrantStore` | Protocol: `roles_for(subject)`, `assign`, `revoke`, `list_assignments`; `InMemoryGrantStore` reference |
| `CombinedResolver` | Union of group roles, stored grants and a `bootstrap` subject → roles map |

The union covers every way a person can be given roles:

- **Groups** answer "what does this person's directory group give them". With local auth the groups come from the
  service's own `LoginViews.authenticate()`.
- **Grants** are in-app assignments, keyed on `Identity.subject`.
- **Bootstrap** covers setup and recovery.

## Settings (planned)

- **`Setting`**: a frozen definition with these fields: `key`, `type` (bool/int/str/choice), `default`, `scope`,
  `label`, `help_text`, `choices`, `min`/`max`, `group`, `edit_permission`.
  - `scope` is `SettingScope.APP` or `SettingScope.USER`.
  - `edit_permission` defaults to `None`.
- **`SettingsRegistry`**: registration, lookup, and `validate`/`coerce` from form strings to typed values.
- **`SettingsStore`**: a Protocol keyed by `(scope, subject | None, key)`, with `get_many`, `set` and `delete`.
  `InMemorySettingsStore` and `JsonFileSettingsStore` are the reference implementations.
- **`Settings(registry, store)`**: the facade, with `effective(identity)`, `get`, `set_user` and
  `set_app(..., granted=...)`. `set_app` checks `edit_permission`.

**Resolution order** for a USER setting is: user value, then app value (an admin-set default), then env override,
then the definition's default. An APP setting uses the same chain without the user step.

**Opt-in built-ins** live in `settings.builtins.USER_PREFERENCES`:

- `ui.theme` (light/dark/system)
- `locale.timezone`
- `locale.date_format`
- `ui.page_size`

Further shared settings, such as compact density, are a separate scoping item.

## Storage tables (planned, `[sqlalchemy]` extra)

`gth_settings` and `gth_role_grants` are defined on a `MetaData` the service passes in, so its own Alembic migrates
them. `SQLAlchemySettingsStore` and `SQLAlchemyGrantStore` both take a session factory. The contracts run against
every store.
