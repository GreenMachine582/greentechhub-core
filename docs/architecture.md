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
│   │   ├── models.py              # Identity, User, Claims, Scope, Group
│   │   └── provider.py            # IdentityProvider protocol + DevelopmentIdentityProvider; AuthentikIdentityProvider planned (v0.5)
│   ├── permissions/
│   │   ├── catalogue.py           # typed permission-string helpers (e.g. "portfolio.view")
│   │   └── check.py               # has_permission(identity, "portfolio.view")
│   ├── events/
│   │   ├── publish.py
│   │   ├── subscribe.py
│   │   └── types.py
│   ├── feature_flags/
│   │   └── provider.py            # FeatureFlagProvider protocol + env/file-backed impl
│   ├── health/
│   │   ├── checks/
│   │   │   ├── database.py        # planned — lands with first consumer needing it
│   │   │   ├── redis.py           # planned — lands with first consumer needing it
│   │   │   ├── disk.py
│   │   │   └── external.py        # planned — lands with first consumer needing it
│   │   └── result.py              # HealthResult
│   ├── query/
│   │   ├── types.py                # Filter, Operator, Sort, Page, PageRequest
│   │   └── envelope.py            # shared paginated-response shape
│   ├── observability/
│   │   └── otel.py                # planned (v0.6)
│   ├── security/
│   │   ├── passwords.py
│   │   ├── tokens.py
│   │   └── redact.py
│   ├── proxy/
│   │   └── trusted_proxy.py
│   ├── version.py
│   ├── background/
│   │   ├── scheduler.py           # planned (v0.6)
│   │   ├── tasks.py               # planned (v0.6)
│   │   └── locks.py               # planned (v0.6)
│   └── types/
│       └── common.py              # FlashMessage, Result, etc.
├── tests/
├── pyproject.toml
└── README.md
```

See [docs/identity.md](identity.md) for the identity model, 
[docs/permissions.md](permissions.md), [docs/events.md](events.md), [docs/query.md](query.md), and 
[docs/health.md](health.md) for the higher-detail modules, and [docs/modules.md](modules.md) for the rest.
