import asyncio

import pytest

from greentechhub_core.identity.models import Identity, RawAuthContext
from greentechhub_core.identity.provider import DevelopmentIdentityProvider
from greentechhub_core.permissions import (
    InMemoryGrantStore,
    Permission,
    Role,
    RoleResolver,
    has_permission,
)

VIEW = Permission("reports.view")
EDIT = Permission("reports.edit")
MANAGE = Permission("settings.manage")

VIEWER = Role(name="viewer", permissions={VIEW})
EDITOR = Role(name="editor", permissions={VIEW, EDIT})
ADMIN = Role(name="admin", permissions={VIEW, EDIT, MANAGE})
ROLES = (VIEWER, EDITOR, ADMIN)
_KEY = "k" * 32


def _identity(subject: str = "alice", groups: list[str] | None = None) -> Identity:
    return Identity(subject=subject, username=subject, email=None, groups=groups or [], claims={})


# sources, one at a time


def test_group_roles_grant_the_mapped_roles_permissions():
    resolver = RoleResolver(roles=ROLES, group_roles={"staff": ["editor"]})
    assert resolver.granted_sync(_identity(groups=["staff"])) == frozenset({VIEW, EDIT})


def test_groups_the_identity_does_not_carry_grant_nothing():
    resolver = RoleResolver(roles=ROLES, group_roles={"staff": ["editor"]})
    assert resolver.granted_sync(_identity(groups=["other"])) == frozenset()


def test_bootstrap_grants_by_subject_with_no_groups():
    resolver = RoleResolver(roles=ROLES, bootstrap={"alice": ["admin"]})
    assert resolver.granted_sync(_identity("alice")) == ADMIN.permissions
    assert resolver.granted_sync(_identity("bob")) == frozenset()


def test_stored_grants_are_read_by_subject():
    store = InMemoryGrantStore()
    store.assign_sync("bob", "viewer")
    resolver = RoleResolver(roles=ROLES, grants=store)
    assert resolver.granted_sync(_identity("bob")) == frozenset({VIEW})


def test_grant_changes_apply_on_the_next_resolve():
    store = InMemoryGrantStore()
    resolver = RoleResolver(roles=ROLES, grants=store)
    store.assign_sync("bob", "admin")
    assert MANAGE in resolver.granted_sync(_identity("bob"))
    store.revoke_sync("bob", "admin")
    assert resolver.granted_sync(_identity("bob")) == frozenset()


# union


def test_all_three_sources_union():
    store = InMemoryGrantStore({"alice": {"viewer"}})
    resolver = RoleResolver(
        roles=ROLES,
        group_roles={"staff": ["editor"]},
        bootstrap={"alice": ["admin"]},
        grants=store,
    )
    identity = _identity("alice", groups=["staff"])
    assert resolver.roles_for_sync(identity) == frozenset({"viewer", "editor", "admin"})
    assert resolver.granted_sync(identity) == frozenset({VIEW, EDIT, MANAGE})


def test_overlapping_roles_deduplicate():
    resolver = RoleResolver(roles=ROLES, group_roles={"a": ["viewer"], "b": ["viewer", "editor"]})
    identity = _identity(groups=["a", "b"])
    assert resolver.roles_for_sync(identity) == frozenset({"viewer", "editor"})
    assert resolver.granted_sync(identity) == frozenset({VIEW, EDIT})


def test_granted_feeds_has_permission():
    resolver = RoleResolver(roles=ROLES, bootstrap={"alice": ["editor"]})
    identity = _identity("alice")
    granted = resolver.granted_sync(identity)
    assert has_permission(identity, EDIT, granted=granted) is True
    assert has_permission(identity, MANAGE, granted=granted) is False


# empty / anonymous


def test_anonymous_resolves_to_nothing():
    resolver = RoleResolver(roles=ROLES, bootstrap={"alice": ["admin"]})
    assert resolver.roles_for_sync(None) == frozenset()
    assert resolver.granted_sync(None) == frozenset()


def test_roles_only_resolver_grants_nothing():
    resolver = RoleResolver(roles=ROLES)
    assert resolver.granted_sync(_identity(groups=["admin"])) == frozenset()


def test_no_roles_at_all_is_allowed_and_grants_nothing():
    assert RoleResolver(roles=()).granted_sync(_identity()) == frozenset()


# construction validation


def test_duplicate_role_names_are_rejected():
    with pytest.raises(ValueError, match="duplicate role name 'admin'"):
        RoleResolver(roles=(ADMIN, Role(name="admin", permissions=set())))


def test_group_roles_naming_an_unknown_role_is_rejected():
    with pytest.raises(ValueError, match=r"group_roles\['staff'\].*'editr'"):
        RoleResolver(roles=ROLES, group_roles={"staff": ["editr"]})


def test_bootstrap_naming_an_unknown_role_is_rejected():
    with pytest.raises(ValueError, match=r"bootstrap\['alice'\].*'superuser'"):
        RoleResolver(roles=ROLES, bootstrap={"alice": ["superuser"]})


def test_unknown_role_names_from_grants_are_ignored():
    store = InMemoryGrantStore({"bob": {"retired-role", "viewer"}})
    resolver = RoleResolver(roles=ROLES, grants=store)
    assert resolver.roles_for_sync(_identity("bob")) == frozenset({"viewer"})
    assert resolver.granted_sync(_identity("bob")) == frozenset({VIEW})


def test_mapping_values_can_be_any_iterable():
    resolver = RoleResolver(
        roles=ROLES, group_roles={"staff": ("viewer",)}, bootstrap={"alice": {"editor"}}
    )
    assert resolver.roles_for_sync(_identity("alice", ["staff"])) == frozenset({"viewer", "editor"})


# async


def test_async_matches_sync_including_grants():
    store = InMemoryGrantStore({"alice": {"viewer"}})
    resolver = RoleResolver(roles=ROLES, group_roles={"staff": ["editor"]}, grants=store)
    identity = _identity("alice", ["staff"])
    assert asyncio.run(resolver.roles_for(identity)) == resolver.roles_for_sync(identity)
    assert asyncio.run(resolver.granted(identity)) == resolver.granted_sync(identity)
    assert asyncio.run(resolver.granted(None)) == frozenset()


# no Authentik: identities from core's own local/dev provider


def test_development_identity_provider_groups_map_to_roles():
    identity = DevelopmentIdentityProvider(secret_key=_KEY).resolve_sync(
        RawAuthContext(dev_mode=True)
    )
    assert identity is not None
    resolver = RoleResolver(roles=ROLES, group_roles={"dev": ["admin"]})
    assert resolver.granted_sync(identity) == ADMIN.permissions


def test_local_auth_bootstrap_admin_with_no_groups():
    provider = DevelopmentIdentityProvider(secret_key=_KEY)
    token = provider.issue(_identity("local-admin"))
    identity = provider.resolve_sync(RawAuthContext(token=token))
    assert identity is not None
    assert identity.groups == []
    resolver = RoleResolver(roles=ROLES, bootstrap={"local-admin": ["admin"]})
    assert MANAGE in resolver.granted_sync(identity)
