"""permissions.resolver — PermissionResolver and RoleResolver: turning an
identity into the flat `granted` set has_permission (check.py) checks
against — see docs/permissions.md.

Opt-in: nothing here runs unless a service constructs a RoleResolver with
its own Roles. This package still defines no roles or permission values —
the service passes its catalogue in.

No Authentik dependency: RoleResolver reads only `subject` and `groups` off
whatever identity it's given (IdentityLike below), so an Identity from local
auth, DevelopmentIdentityProvider, or forward auth all work the same. Three
sources feed a person's roles, unioned:
  - group_roles — directory group → role names. Groups come from the
    identity itself: Authentik's header, or whatever a local login sets.
  - bootstrap — subject → role names, fixed in config. Covers first-run
    setup and recovery: the first admin exists before any group or grant
    data does.
  - grants — an optional GrantStore (grants.py) of in-app assignments.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol

from greentechhub_core.permissions.catalogue import Permission, Role
from greentechhub_core.permissions.grants import GrantStore


class IdentityLike(Protocol):
    """The two identity fields role resolution reads. Structural rather than
    importing identity.Identity: this package's top-level modules never
    import each other (see check.py's docstring), and core's own Identity
    satisfies this shape as-is.
    """

    @property
    def subject(self) -> str: ...

    @property
    def groups(self) -> Sequence[str]: ...


class PermissionResolver(Protocol):
    """Structural contract for anything that answers "which permissions
    does this identity hold". `None` (anonymous) always resolves to an empty
    set rather than raising, so an adapter can call it unconditionally.

    Async plus a `_sync` twin, mirroring IdentityProvider's pair.
    """

    async def granted(self, identity: IdentityLike | None) -> frozenset[Permission]: ...

    def granted_sync(self, identity: IdentityLike | None) -> frozenset[Permission]: ...


def _role_names(mapping: Mapping[str, Iterable[str]] | None) -> dict[str, frozenset[str]]:
    return {key: frozenset(names) for key, names in (mapping or {}).items()}


class RoleResolver:
    """The PermissionResolver this package ships: roles from groups,
    bootstrap and grants, flattened to their permissions.

    Args:
        roles: the service's own Role catalogue. Role names must be unique.
        group_roles: group name → role names. A group the identity doesn't
            carry contributes nothing.
        bootstrap: subject → role names, for first-run setup and recovery.
        grants: an optional GrantStore of in-app role assignments.

    Construction fails fast with ValueError on a duplicate role name, or a
    `group_roles`/`bootstrap` entry naming a role not in `roles` — config
    typos surface at startup, like EnvFileFeatureFlagProvider's malformed
    config. Role names read back from `grants` at request time are *not*
    validated: a name that isn't in `roles` (say, a role deleted from code
    while its grant rows remain) is ignored, since it can't grant anything.

    With only `roles` given, every identity resolves to nothing — a safe
    default.
    """

    def __init__(
        self,
        *,
        roles: Iterable[Role],
        group_roles: Mapping[str, Iterable[str]] | None = None,
        bootstrap: Mapping[str, Iterable[str]] | None = None,
        grants: GrantStore | None = None,
    ) -> None:
        self._roles: dict[str, Role] = {}
        for role in roles:
            if role.name in self._roles:
                raise ValueError(f"duplicate role name {role.name!r}")
            self._roles[role.name] = role
        self._group_roles = _role_names(group_roles)
        self._bootstrap = _role_names(bootstrap)
        for source, mapping in (("group_roles", self._group_roles), ("bootstrap", self._bootstrap)):
            for key, names in mapping.items():
                unknown = sorted(names - self._roles.keys())
                if unknown:
                    raise ValueError(f"{source}[{key!r}] names unknown role(s): {unknown}")
        self._grants = grants

    def _config_roles(self, identity: IdentityLike) -> frozenset[str]:
        names: set[str] = set(self._bootstrap.get(identity.subject, ()))
        for group in identity.groups:
            names |= self._group_roles.get(group, frozenset())
        return frozenset(names)

    def _known(self, names: Iterable[str]) -> frozenset[str]:
        return frozenset(name for name in names if name in self._roles)

    def _permissions(self, names: frozenset[str]) -> frozenset[Permission]:
        return frozenset().union(*(self._roles[name].permissions for name in names))

    def roles_for_sync(self, identity: IdentityLike | None) -> frozenset[str]:
        """The names of every known role `identity` holds, from all sources."""
        if identity is None:
            return frozenset()
        names = self._config_roles(identity)
        if self._grants is not None:
            names |= self._grants.roles_for_sync(identity.subject)
        return self._known(names)

    async def roles_for(self, identity: IdentityLike | None) -> frozenset[str]:
        if identity is None:
            return frozenset()
        names = self._config_roles(identity)
        if self._grants is not None:
            names |= await self._grants.roles_for(identity.subject)
        return self._known(names)

    def granted_sync(self, identity: IdentityLike | None) -> frozenset[Permission]:
        return self._permissions(self.roles_for_sync(identity))

    async def granted(self, identity: IdentityLike | None) -> frozenset[Permission]:
        return self._permissions(await self.roles_for(identity))
