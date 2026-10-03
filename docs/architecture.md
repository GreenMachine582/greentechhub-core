[← Back to README](../README.md)

# 🏗️ Architecture

## Layered architecture

```
                    greentechhub-core
   (config, logging, identity, permissions, events, feature_flags,
    health checks, query contracts, observability, security, proxy,
    version, background, types/utils — zero web-framework imports)
                           ▲
              ┌────────────┴────────────┐
              │                         │
    greentechhub-fastapi        greentechhub-django
    (middleware, auth DI,       (middleware, context
     health router, query       processors, messages
     adapter, exception         bridge, auth bridge,
     handlers, flash,           health view, settings
     registration helpers)      shim)
```

Each arrow is a real dependency (`greentechhub-fastapi` depends on `greentechhub-core`; it does not reimplement 
anything core already provides). Services then consume `greentechhub-core` indirectly, through whichever adapter 
matches their framework. A CLI tool, a background worker, or a future non-web service can depend on `greentechhub-core` 
alone.

## Package layout

```
greentechhub-core/
├── src/greentechhub_core/
│   ├── config/
│   │   └── base_settings.py       # GTHBaseSettings
│   ├── logging/
│   │   └── setup.py
│   ├── identity/
│   │   ├── models.py              # Identity, RawAuthContext
│   │   └── provider.py            # IdentityProvider protocol + DevelopmentIdentityProvider + AuthentikIdentityProvider
│   ├── permissions/
│   │   ├── catalogue.py           # typed permission-string helpers (e.g. "portfolio.view")
│   │   ├── check.py               # has_permission(identity, "portfolio.view", granted=...)
│   │   ├── resolver.py            # PermissionResolver protocol + RoleResolver (groups/bootstrap/grants → granted)
│   │   └── grants.py              # GrantStore protocol + InMemoryGrantStore
│   ├── settings/
│   │   ├── definitions.py         # SettingScope, SettingType, Setting (validate/coerce)
│   │   ├── registry.py            # SettingsRegistry
│   │   ├── resolution.py          # user → app → env → default; env overrides (SETTING_UI__PAGE_SIZE)
│   │   ├── builtins.py            # opt-in USER_PREFERENCES: theme, density, motion, sidebar, timezone, date/number/time formats, page size
│   │   ├── store.py               # SettingsStore protocol + InMemorySettingsStore + JsonFileSettingsStore
│   │   ├── secrets.py             # SecretCipher protocol, SECRET_SET marker, SecretDecryptError
│   │   ├── crypto.py              # FernetCipher — optional `[crypto]` extra
│   │   └── service.py             # Settings facade: effective/get, set_user, set_app (edit_permission check), get_secret
│   ├── events/
│   │   ├── publish.py
│   │   ├── subscribe.py
│   │   └── types.py
│   ├── feature_flags/
│   │   └── provider.py            # FeatureFlagProvider protocol + env/file-backed impl
│   ├── health/
│   │   ├── checks/
│   │   │   ├── database.py        # check_database — duck-typed on a SQLAlchemy-like engine, or a plain ping callable
│   │   │   ├── redis.py           # planned — lands when Redis is deployed for some other reason
│   │   │   ├── disk.py
│   │   │   └── external.py        # check_external — duck-typed on an injected client (e.g. httpx.AsyncClient)
│   │   └── result.py              # HealthResult
│   ├── query/
│   │   ├── types.py                # Filter, Operator, Sort, Page, PageRequest
│   │   └── envelope.py            # shared paginated-response shape
│   ├── observability/
│   │   ├── resource.py            # get_resource_attributes — service.name/service.version, no OTel import
│   │   └── otel.py                # planned (v0.6) — TracerProvider/MeterProvider/exporter setup, once a collector exists
│   ├── security/
│   │   ├── passwords.py
│   │   ├── tokens.py
│   │   └── redact.py
│   ├── proxy/
│   │   └── trusted_proxy.py
│   ├── version.py
│   ├── background/
│   │   ├── scheduler.py           # planned — deferred until a consumer needs ≥2 scheduled jobs
│   │   ├── tasks.py               # planned — deferred until a consumer needs ≥2 scheduled jobs
│   │   └── locks.py               # Lock protocol + FileLock (OS-advisory-lock-backed)
│   ├── sqlalchemy/                # optional `[sqlalchemy]` extra
│   │   ├── tables.py              # settings_table/role_grants_table on the service's MetaData
│   │   ├── settings.py            # SQLAlchemySettingsStore
│   │   └── grants.py              # SQLAlchemyGrantStore
│   ├── contracts/                 # pytest contract bases (the `contracts` extra): identity, feature flags, health, query, permissions, settings
│   └── types/
│       ├── common.py              # FlashMessage, Result, etc.
│       └── errors.py              # ApplicationError and its HTTP-shaped subclasses (docs/modules.md#errors)
├── tests/
├── pyproject.toml
└── README.md
```

See [docs/identity.md](identity.md) for the identity model, 
[docs/permissions.md](permissions.md), [docs/settings.md](settings.md), [docs/events.md](events.md), [docs/query.md](query.md), and 
[docs/health.md](health.md) for the higher-detail modules, and [docs/modules.md](modules.md) for the rest.
