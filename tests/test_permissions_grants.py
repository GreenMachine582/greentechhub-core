from greentechhub_core.permissions import InMemoryGrantStore

# InMemoryGrantStore-specific behaviour — the shared semantics live in
# GrantStoreContract (tests/test_contracts_permissions.py).


def test_initial_assignments_are_loaded():
    store = InMemoryGrantStore({"alice": {"admin"}, "bob": frozenset({"viewer"})})
    assert store.roles_for_sync("alice") == frozenset({"admin"})
    assert store.roles_for_sync("bob") == frozenset({"viewer"})


def test_initial_subjects_with_no_roles_are_dropped():
    store = InMemoryGrantStore({"alice": set(), "bob": {"viewer"}})
    assert dict(store.list_assignments_sync()) == {"bob": frozenset({"viewer"})}


def test_initial_assignments_are_copied():
    roles = {"admin"}
    store = InMemoryGrantStore({"alice": roles})
    roles.add("editor")
    assert store.roles_for_sync("alice") == frozenset({"admin"})


def test_reads_are_copies_not_live_state():
    store = InMemoryGrantStore({"alice": {"admin"}})
    listing = store.list_assignments_sync()
    store.assign_sync("alice", "editor")
    assert listing["alice"] == frozenset({"admin"})
    assert isinstance(store.roles_for_sync("alice"), frozenset)


def test_revoking_the_last_role_drops_the_subject():
    store = InMemoryGrantStore({"alice": {"admin"}})
    store.revoke_sync("alice", "admin")
    assert "alice" not in store.list_assignments_sync()
