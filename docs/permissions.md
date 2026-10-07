[← Back to README](../README.md)

# 🔑 Permissions: Global Roles vs. Application Permissions

This module distinguishes two different things:

- **Global roles/groups** — owned by the identity source (Authentik, or a service's own local login), live in [`Identity.groups`](identity.md) (e.g. `homelab-users`, `admin-users`). On their own they answer "is this person allowed into this application at all". A service can *opt in* to mapping a group onto one of its own roles (`RoleResolver`'s `group_roles`, below), but it doesn't have to.
- **Application permissions** — owned by each service, stored in that service's own database (each service already owns its own `User`/permissions table; that's where permissions like `portfolio.view`, `import.run`, `reports.view` belong, not in Authentik or in `greentechhub-core`).

`greentechhub-core`'s `permissions` module deliberately does **not** store per-service grants or define any roles — that would create three places defining the same thing (Authentik, the service DB, and this package), which is duplication this module avoids by design. Instead it provides:

- A typed way to declare a permission string (`portfolio.view`), so services get typo-safety and a single place per-service to see the full catalogue.
- `has_permission(identity, permission, granted=...)` — a check primitive; `granted` is whatever the calling service looks up from its own storage, or what `RoleResolver` builds for it (below).
- A `Role` = bundle-of-permissions helper (`Trader = {portfolio.view, portfolio.edit, reports.view}`), so services can evolve from permissions rather than hardcoding role checks — but the bundle definition and the grant itself still live in the service, not in this package.
- `RoleResolver`, `PermissionResolver` and `GrantStore` — opt-in resolution from groups, a bootstrap map and stored grants to `granted`. The service supplies the roles and, if it wants persistent grants, the store over its own database ([below](#resolving-granted-permissions)).

The permission catalogue format is a plain `resource.action` string convention — typed helpers give typo-safety, and it's simple enough for a single per-service catalogue to stay readable as it grows.

## Resolving granted permissions

`has_permission` checks against a flat `granted` set. `RoleResolver` builds that set from any identity. It is opt-in and needs no Authentik: it reads only `Identity.subject` and `Identity.groups`, so identities from local auth, `DevelopmentIdentityProvider` and forward auth all work.

A person's roles are the union of three sources:

| Source | Keyed on | Use it for |
|---|---|---|
| `group_roles` | a group on the identity | Directory groups (Authentik, or whatever a local login puts in `groups`) |
| `bootstrap` | `Identity.subject` | First-run setup and recovery. The first admin exists before any group or grant data |
| `grants` | `Identity.subject` | In-app assignments held in a `GrantStore` |

```python
from greentechhub_core.permissions import InMemoryGrantStore, Role, RoleResolver, has_permission

ADMIN = Role(name="admin", permissions={SETTINGS_MANAGE, REPORTS_VIEW})   # the service's own catalogue
VIEWER = Role(name="viewer", permissions={REPORTS_VIEW})

resolver = RoleResolver(
    roles=[ADMIN, VIEWER],
    group_roles={"admin-users": ["admin"]},   # optional
    bootstrap={"local-admin": ["admin"]},     # optional: works with local auth alone
    grants=InMemoryGrantStore(),              # optional: or a store over the service's own DB
)
granted = resolver.granted_sync(identity)     # or: await resolver.granted(identity)
has_permission(identity, SETTINGS_MANAGE, granted=granted)
```

**Role maps from settings.** `parse_role_map(value, name)` turns `ROLE_GROUPS`/`ROLE_BOOTSTRAP` into the dicts
above. It accepts the compact env form `"alice=admin|editor,bob=viewer"`, a JSON object string, or a mapping.
Empty means no entries, and anything malformed raises `ValueError` naming the setting. `read_role_map(settings,
name)` reads the setting first (`config.setting_value`).

- **Fails fast.** A duplicate role name, or a `group_roles`/`bootstrap` entry naming an unknown role, raises `ValueError` at construction.
- **Ignores stale grants.** A stored role name that isn't in `roles` grants nothing and is skipped. This covers a role deleted from code while its rows remain.
- **Handles anonymous users.** `None` resolves to an empty set, so an adapter can call the resolver unconditionally.
- **Grants nothing by default.** A resolver given only `roles` grants nothing until one of the sources is configured.

**Where grants live.** `GrantStore` is a protocol over `(subject, role name)` pairs. `InMemoryGrantStore` is its reference implementation, for tests and single-process tools. Persistent grants live in the *service's own* database, through a store implementing the protocol. Core still holds no grant data and defines no roles or permission values, so the "three places" duplication above doesn't come back.

**Contracts.** `PermissionResolverContract` and `GrantStoreContract` (in `greentechhub_core.contracts`) check any implementation. See [docs/testing.md](testing.md).
