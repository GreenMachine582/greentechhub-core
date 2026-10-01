"""contracts.permissions — PermissionResolverContract and GrantStoreContract:
shared conformance coverage for any PermissionResolver or GrantStore (this
package's own RoleResolver/InMemoryGrantStore, or a service's database-backed
store) — see docs/testing.md.

PermissionResolverContract needs two fixtures:
    resolver: a constructed PermissionResolver.
    granted_identity: an identity (anything with `subject` and `groups`)
        this resolver grants at least one permission to.

GrantStoreContract needs one fixture:
    store: an empty GrantStore — the tests assign and revoke their own
        subjects and assert on list_assignments as a whole.
"""

import asyncio

from greentechhub_core.identity.models import Identity
from greentechhub_core.permissions import GrantStore, Permission, PermissionResolver
from greentechhub_core.permissions.resolver import IdentityLike

_NOBODY = Identity(
    subject="definitely-unknown-subject-xyz", username="nobody", email=None, groups=[], claims={}
)
_GARBAGE = Identity(
    subject="",
    username="garbage",
    email=None,
    groups=["", " ", "a b/c!", "🔥", "definitely-unknown-group"],
    claims={},
)


class PermissionResolverContract:
    """Inherit this class in a test module, defining `resolver` and
    `granted_identity` as pytest fixtures, to run the shared
    PermissionResolver conformance suite against a concrete implementation.
    """

    def test_anonymous_resolves_to_an_empty_frozenset(self, resolver: PermissionResolver) -> None:
        assert resolver.granted_sync(None) == frozenset()
        assert isinstance(resolver.granted_sync(None), frozenset)

    def test_unknown_identity_resolves_to_an_empty_frozenset(
        self, resolver: PermissionResolver
    ) -> None:
        assert resolver.granted_sync(_NOBODY) == frozenset()

    def test_garbage_subject_and_groups_never_raise(self, resolver: PermissionResolver) -> None:
        resolver.granted_sync(_GARBAGE)

    def test_granted_identity_resolves_to_permissions(
        self, resolver: PermissionResolver, granted_identity: IdentityLike
    ) -> None:
        granted = resolver.granted_sync(granted_identity)
        assert isinstance(granted, frozenset)
        assert granted
        assert all(isinstance(p, Permission) for p in granted)

    def test_granted_and_granted_sync_agree(
        self, resolver: PermissionResolver, granted_identity: IdentityLike
    ) -> None:
        for identity in (None, _NOBODY, granted_identity):
            assert asyncio.run(resolver.granted(identity)) == resolver.granted_sync(identity)


class GrantStoreContract:
    """Inherit this class in a test module, defining `store` (empty) as a
    pytest fixture, to run the shared GrantStore conformance suite against a
    concrete implementation.
    """

    def test_unknown_subject_has_no_roles(self, store: GrantStore) -> None:
        assert store.roles_for_sync("unknown") == frozenset()

    def test_assigned_role_reads_back(self, store: GrantStore) -> None:
        store.assign_sync("alice", "admin")
        assert store.roles_for_sync("alice") == frozenset({"admin"})

    def test_assign_is_idempotent(self, store: GrantStore) -> None:
        store.assign_sync("alice", "admin")
        store.assign_sync("alice", "admin")
        assert store.roles_for_sync("alice") == frozenset({"admin"})

    def test_revoke_removes_only_that_role(self, store: GrantStore) -> None:
        store.assign_sync("alice", "admin")
        store.assign_sync("alice", "editor")
        store.revoke_sync("alice", "admin")
        assert store.roles_for_sync("alice") == frozenset({"editor"})

    def test_revoking_a_role_not_held_is_a_no_op(self, store: GrantStore) -> None:
        store.revoke_sync("nobody", "admin")
        store.assign_sync("alice", "editor")
        store.revoke_sync("alice", "admin")
        assert store.roles_for_sync("alice") == frozenset({"editor"})

    def test_subjects_are_isolated(self, store: GrantStore) -> None:
        store.assign_sync("alice", "admin")
        assert store.roles_for_sync("bob") == frozenset()

    def test_list_assignments_reflects_the_store(self, store: GrantStore) -> None:
        store.assign_sync("alice", "admin")
        store.assign_sync("bob", "editor")
        store.assign_sync("carol", "editor")
        store.revoke_sync("carol", "editor")
        assert dict(store.list_assignments_sync()) == {
            "alice": frozenset({"admin"}),
            "bob": frozenset({"editor"}),
        }

    def test_async_and_sync_agree(self, store: GrantStore) -> None:
        async def exercise() -> None:
            await store.assign("dave", "admin")
            assert await store.roles_for("dave") == store.roles_for_sync("dave")
            assert dict(await store.list_assignments()) == dict(store.list_assignments_sync())
            await store.revoke("dave", "admin")

        asyncio.run(exercise())
        assert store.roles_for_sync("dave") == frozenset()
