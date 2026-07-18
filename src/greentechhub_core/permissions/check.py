"""permissions.check — has_permission: the single check primitive this
module provides (see docs/permissions.md). Deliberately just one function:
a permission-string containment check against whatever `granted` collection
the calling service already looked up from its own storage — this module
holds no grants of its own (see catalogue.py's module docstring for why).
"""

from collections.abc import Set as AbstractSet

from greentechhub_core.permissions.catalogue import Permission


def has_permission(
    identity: object,
    permission: Permission,
    *,
    granted: AbstractSet[Permission],
) -> bool:
    """Return whether `permission` is present in `granted`.

    Purely `permission in granted` — no group-based bypass logic, and no
    special-casing for a Role object accidentally ending up inside
    `granted` (a service is expected to have already flattened any Role(s)
    into `granted` itself, e.g. `granted = trader_role.permissions |
    extra_perms`, per Role's own docstring in catalogue.py). One code path,
    matching this module's confirmed design decisions.

    `identity` is accepted for signature symmetry with docs/permissions.md's
    own `has_permission(identity, permission, granted=...)` shape, and for a
    plausible future use (e.g. audit-logging which identity a check was
    performed for) — but is never read here: the result depends only on
    `permission`/`granted`. Typed as plain `object`, not
    `identity.Identity`: every existing sibling module in this package
    (health, query, security, identity itself) only ever imports from its
    own submodules, never from another top-level greentechhub_core module —
    importing Identity here for a parameter this function never inspects
    would be this package's first cross-module coupling, for no behavioral
    benefit. `object` (rather than `Any`) is deliberate too: it still lets a
    type checker flag an accidental future attempt to read an attribute off
    `identity` inside this function, guarding the "pass-through only, never
    inspected" contract rather than silently allowing it. A service wanting
    an actual bypass (e.g. an "admin-users" group always passing)
    implements that in its own permission-lookup code before calling
    has_permission, not inside this function.

    `granted` is typed as `collections.abc.Set` (aliased `AbstractSet`), not
    the wider `Collection` — a service's "permissions granted to this user"
    collection is a plausible hot path (checked on every request), and `in`
    on a `Set` is O(1) where `in` on an arbitrary `Collection`/list is O(n);
    narrowing the parameter type documents and enforces (for a type
    checker) that expectation rather than silently degrading to O(n) for a
    caller who passes a list. A caller whose storage layer returns a list
    should wrap it in `set(...)` once (e.g. right after the DB query), not
    on every has_permission call. `frozenset[Permission]` — exactly what
    Role.permissions already produces — satisfies `AbstractSet[Permission]`
    directly, so the intended `granted = some_role.permissions |
    extra_perms` composition needs no extra wrapping.

    Empty `granted` always returns False (nothing is in an empty set).
    """
    return permission in granted
