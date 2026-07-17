[← Back to README](../README.md)

# 🔑 Permissions: Global Roles vs. Application Permissions

This module distinguishes two different things:

- **Global roles/groups** — owned by Authentik, live in [`Identity.groups`](identity.md) (e.g. `homelab-users`, `admin-users`). They answer "is this person allowed into this application at all," not "what can they do inside it."
- **Application permissions** — owned by each service, stored in that service's own database (each service already owns its own `User`/permissions table; that's where permissions like `portfolio.view`, `import.run`, `reports.view` belong, not in Authentik or in `greentechhub-core`).

`greentechhub-core`'s `permissions` module deliberately does **not** store per-service grants — that would create three places defining the same thing (Authentik, the service DB, and this package), which is duplication this module avoids by design. Instead it provides:

- A typed way to declare a permission string (`portfolio.view`), so services get typo-safety and a single place per-service to see the full catalogue.
- `has_permission(identity, permission, granted=...)` — a check primitive; `granted` is whatever the calling service looks up from its own storage.
- A `Role` = bundle-of-permissions helper (`Trader = {portfolio.view, portfolio.edit, reports.view}`), so services can evolve from permissions rather than hardcoding role checks — but the bundle definition and the grant itself still live in the service, not in this package.

The permission catalogue format is a plain `resource.action` string convention — typed helpers give typo-safety, and it's simple enough for a single per-service catalogue to stay readable as it grows.
