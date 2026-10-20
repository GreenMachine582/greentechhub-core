"""contracts.users — UserStoreContract: shared conformance coverage for any
UserStore (this package's InMemoryUserStore and SQLAlchemyUserStore, or a
service's own), including the authenticate/resolve_account rules run over
it — see docs/testing.md.

Needs one fixture:
    store: an empty UserStore whose clock is the contract's `clock` fixture
        (a FakeClock), so the tests can move time on.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from greentechhub_core.contracts.api_tokens import FakeClock
from greentechhub_core.identity.models import Identity
from greentechhub_core.users import (
    LinkExists,
    ProvisioningPolicy,
    UserExists,
    UserStore,
    account_identity,
    authenticate,
    authenticate_sync,
    resolve_account,
    resolve_account_sync,
    set_password_sync,
)

_T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def _authentik(uid: str = "ak-1", username: str = "alice", **fields) -> Identity:
    return Identity(subject=uid, username=username, email=fields.pop("email", None),
                    groups=fields.pop("groups", []), claims={}, provider="authentik", **fields)


class UserStoreContract:
    """Inherit this class in a test module, defining `store` (empty, on the
    `clock` fixture) as a pytest fixture, to run the shared UserStore
    conformance suite against a concrete implementation.
    """

    @pytest.fixture
    def clock(self) -> FakeClock:
        return FakeClock(_T0)

    # accounts

    def test_create_normalizes_and_reads_back(self, store: UserStore) -> None:
        account = store.create_sync(" Alice ", email="Alice@Example.COM", display_name=" Alice A ")
        assert (account.username, account.email, account.display_name) == (
            "alice", "alice@example.com", "Alice A")
        assert len(account.id) == 32 and account.active and not account.email_verified
        assert account.created_at == account.updated_at == _T0
        assert store.get_sync(account.id) == account
        assert store.by_username_sync("ALICE") == account
        assert store.by_email_sync("alice@EXAMPLE.com") == account

    def test_unknown_lookups_are_none(self, store: UserStore) -> None:
        assert store.get_sync("0" * 32) is None
        assert store.by_username_sync("nobody") is None
        assert store.by_email_sync("nobody@example.com") is None
        assert store.by_email_sync("not an email") is None
        assert store.by_username_sync("   ") is None

    def test_username_and_email_are_unique(self, store: UserStore) -> None:
        store.create_sync("alice", email="a@example.com")
        with pytest.raises(UserExists) as clash:
            store.create_sync("ALICE")
        assert clash.value.field == "username"
        with pytest.raises(UserExists) as clash:
            store.create_sync("bob", email="A@example.com")
        assert clash.value.field == "email"
        assert [u.username for u in store.list_users_sync()] == ["alice"]

    def test_accounts_without_email_dont_clash(self, store: UserStore) -> None:
        store.create_sync("alice")
        store.create_sync("bob")
        assert [u.username for u in store.list_users_sync()] == ["alice", "bob"]

    def test_bad_values_are_refused(self, store: UserStore) -> None:
        for username, email in (("", None), ("two words", None), ("alice", "nope")):
            with pytest.raises(ValueError):
                store.create_sync(username, email=email)

    def test_update_changes_and_stamps(self, store: UserStore, clock: FakeClock) -> None:
        account = store.create_sync("alice", email="a@example.com", email_verified=True)
        clock.advance(minutes=5)
        updated = store.update_sync(account.id, {"display_name": "Alice", "active": False})
        assert updated is not None
        assert (updated.display_name, updated.active) == ("Alice", False)
        assert updated.updated_at == _T0 + timedelta(minutes=5)
        assert store.get_sync(account.id) == updated

    def test_a_changed_email_is_unverified(self, store: UserStore) -> None:
        account = store.create_sync("alice", email="a@example.com", email_verified=True)
        assert store.update_sync(account.id, {"email": "b@example.com"}).email_verified is False
        vouched = store.update_sync(account.id, {"email": "c@example.com", "email_verified": True})
        assert vouched.email_verified is True
        assert store.update_sync(account.id, {"email": None}).email_verified is False

    def test_a_login_alone_leaves_updated_at(self, store: UserStore, clock: FakeClock) -> None:
        account = store.create_sync("alice")
        clock.advance(hours=1)
        updated = store.update_sync(account.id, {"last_login_at": clock()})
        assert updated.last_login_at == _T0 + timedelta(hours=1)
        assert updated.updated_at == _T0

    def test_update_refuses_clashes_and_unknown_fields(self, store: UserStore) -> None:
        store.create_sync("alice", email="a@example.com")
        bob = store.create_sync("bob")
        with pytest.raises(UserExists):
            store.update_sync(bob.id, {"username": "Alice"})
        with pytest.raises(UserExists):
            store.update_sync(bob.id, {"email": "A@example.com"})
        with pytest.raises(ValueError):
            store.update_sync(bob.id, {"id": "x"})
        assert store.get_sync(bob.id) == bob
        assert store.update_sync("0" * 32, {"active": False}) is None

    def test_password_hash_is_kept_out_of_repr(self, store: UserStore) -> None:
        account = set_password_sync(store, store.create_sync("alice").id, "hunter2!")
        assert account.password_hash and account.password_hash not in repr(account)

    # links

    def test_link_find_and_unlink(self, store: UserStore) -> None:
        account = store.create_sync("alice")
        link = store.link_sync(account.id, "authentik", "ak-1")
        assert (link.user_id, link.created_at, link.last_seen_at) == (account.id, _T0, None)
        assert store.find_link_sync("authentik", "ak-1") == link
        assert store.links_for_sync(account.id) == [link]
        with pytest.raises(LinkExists):
            store.link_sync(store.create_sync("bob").id, "authentik", "ak-1")
        assert store.unlink_sync("authentik", "ak-1") is True
        assert store.unlink_sync("authentik", "ak-1") is False
        assert store.find_link_sync("authentik", "ak-1") is None

    def test_link_needs_an_account(self, store: UserStore) -> None:
        with pytest.raises(KeyError):
            store.link_sync("0" * 32, "authentik", "ak-1")

    def test_create_with_a_taken_link_adds_nothing(self, store: UserStore) -> None:
        store.create_sync("alice", link=("authentik", "ak-1"))
        with pytest.raises(LinkExists):
            store.create_sync("bob", link=("authentik", "ak-1"))
        assert store.by_username_sync("bob") is None

    def test_touch_link(self, store: UserStore, clock: FakeClock) -> None:
        store.create_sync("alice", link=("authentik", "ak-1"))
        clock.advance(minutes=3)
        store.touch_link_sync("authentik", "ak-1")
        assert store.find_link_sync("authentik", "ak-1").last_seen_at == _T0 + timedelta(minutes=3)

    # authenticate

    def test_authenticate(self, store: UserStore, clock: FakeClock) -> None:
        account = set_password_sync(store, store.create_sync("alice").id, "hunter2!")
        clock.advance(minutes=1)
        signed_in = authenticate_sync(store, "Alice", "hunter2!")
        assert signed_in is not None and signed_in.id == account.id
        assert signed_in.last_login_at == _T0 + timedelta(minutes=1)
        assert authenticate_sync(store, "alice", "wrong") is None
        assert authenticate_sync(store, "nobody", "hunter2!") is None
        assert authenticate_sync(store, "", "hunter2!") is None

    def test_authenticate_refuses_inactive_and_passwordless(self, store: UserStore) -> None:
        account = set_password_sync(store, store.create_sync("alice").id, "hunter2!")
        store.update_sync(account.id, {"active": False})
        assert authenticate_sync(store, "alice", "hunter2!") is None
        store.create_sync("idp-only")
        assert authenticate_sync(store, "idp-only", "") is None

    def test_authenticate_async_agrees(self, store: UserStore) -> None:
        set_password_sync(store, store.create_sync("alice").id, "hunter2!")
        assert asyncio.run(authenticate(store, "alice", "hunter2!")) is not None
        assert asyncio.run(authenticate(store, "alice", "nope")) is None

    # resolve_account

    def test_local_identity_resolves_to_its_account(self, store: UserStore) -> None:
        account = store.create_sync("alice")
        resolved = resolve_account_sync(store, account_identity(account))
        assert resolved.account == account and resolved.outcome == "existing"
        store.update_sync(account.id, {"active": False})
        assert resolve_account_sync(store, account_identity(account)) is None

    def test_first_sign_in_provisions_a_linked_account(self, store: UserStore) -> None:
        external = _authentik(email="Alice@example.com", email_verified=True, display_name="Alice")
        resolved = resolve_account_sync(store, external)
        assert resolved.outcome == "provisioned"
        account = resolved.account
        assert (account.username, account.email, account.email_verified, account.display_name,
                account.auth_source) == ("alice", "alice@example.com", True, "Alice", "authentik")
        assert account.last_login_at == _T0
        assert store.find_link_sync("authentik", "ak-1").user_id == account.id
        again = resolve_account_sync(store, external)
        assert again.account.id == account.id and again.outcome == "existing"

    def test_idp_owned_fields_sync(self, store: UserStore) -> None:
        first = resolve_account_sync(store, _authentik(email="a@example.com", email_verified=True))
        renamed = _authentik(username="alice2", email="new@example.com", email_verified=True,
                             display_name="Alice Two")
        resolved = resolve_account_sync(store, renamed)
        assert resolved.outcome == "synced" and resolved.account.id == first.account.id
        assert (resolved.account.email, resolved.account.display_name) == (
            "new@example.com", "Alice Two")
        assert resolved.account.username == "alice"  # not IdP-owned by default
        owned = ProvisioningPolicy(idp_owned=frozenset({"username"}))
        assert resolve_account_sync(store, renamed, owned).account.username == "alice2"

    def test_a_blank_idp_field_never_clears(self, store: UserStore) -> None:
        resolve_account_sync(store, _authentik(email="a@example.com", display_name="Alice"))
        resolved = resolve_account_sync(store, _authentik())
        assert resolved.outcome == "existing"
        assert (resolved.account.email, resolved.account.display_name) == ("a@example.com", "Alice")

    def test_usernames_and_emails_already_taken(self, store: UserStore) -> None:
        local = store.create_sync("alice", email="a@example.com")
        resolved = resolve_account_sync(store, _authentik(email="a@example.com",
                                                          email_verified=True))
        assert resolved.outcome == "provisioned" and resolved.account.id != local.id
        assert resolved.account.username == "alice-2" and resolved.account.email is None
        bob = resolve_account_sync(store, _authentik(uid="ak-2", username="bob"))
        moved = resolve_account_sync(store, _authentik(uid="ak-2", username="bob",
                                                       email="a@example.com"))
        assert moved.account.id == bob.account.id and moved.account.email is None

    def test_link_by_verified_email(self, store: UserStore) -> None:
        local = store.create_sync("alice", email="a@example.com")
        policy = ProvisioningPolicy(link_by_verified_email=True)
        unverified = resolve_account_sync(store, _authentik(uid="ak-9", email="a@example.com"),
                                          policy)
        assert unverified.account.id != local.id
        resolved = resolve_account_sync(
            store, _authentik(email="a@example.com", email_verified=True), policy)
        assert resolved.outcome == "linked" and resolved.account.id == local.id
        assert resolved.account.email_verified is True

    def test_without_auto_provision_unlinked_is_none(self, store: UserStore) -> None:
        policy = ProvisioningPolicy(auto_provision=False)
        assert resolve_account_sync(store, _authentik(), policy) is None
        assert store.list_users_sync() == []

    def test_an_inactive_linked_account_is_refused(self, store: UserStore) -> None:
        resolved = resolve_account_sync(store, _authentik())
        store.update_sync(resolved.account.id, {"active": False})
        assert resolve_account_sync(store, _authentik()) is None

    def test_sign_ins_touch_once_per_interval(self, store: UserStore, clock: FakeClock) -> None:
        resolve_account_sync(store, _authentik())
        clock.advance(minutes=30)
        assert resolve_account_sync(store, _authentik()).account.last_login_at == _T0
        clock.advance(minutes=30)
        account = resolve_account_sync(store, _authentik()).account
        assert account.last_login_at == _T0 + timedelta(hours=1)
        assert store.find_link_sync("authentik", "ak-1").last_seen_at == _T0 + timedelta(hours=1)

    def test_resolve_async_agrees(self, store: UserStore) -> None:
        resolved = asyncio.run(resolve_account(store, _authentik(display_name="Alice")))
        assert resolved.outcome == "provisioned"
        again = asyncio.run(resolve_account(store, _authentik(display_name="Alice")))
        assert again.account.id == resolved.account.id

    def test_canonical_identity(self, store: UserStore) -> None:
        external = _authentik(email="a@example.com", email_verified=True, display_name="Alice",
                              groups=["admins"])
        account = resolve_account_sync(store, external).account
        identity = account_identity(account, external)
        assert (identity.subject, identity.username, identity.email, identity.display_name,
                identity.email_verified, identity.groups, identity.provider) == (
            account.id, "alice", "a@example.com", "Alice", True, ["admins"], "authentik")
