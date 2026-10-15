"""contracts.api_tokens — ApiTokenStoreContract: shared conformance coverage
for any ApiTokenStore (this package's InMemoryApiTokenStore and
SQLAlchemyApiTokenStore, or a service's own) — see docs/testing.md.

Needs one fixture:
    store: an empty ApiTokenStore whose clock is the contract's `clock`
        fixture (a FakeClock), so the tests can move time on.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from greentechhub_core.security.api_tokens import ApiTokenStore
from greentechhub_core.security.one_time import token_hash

_T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


class FakeClock:
    """A clock that stands still until `advance` moves it."""

    def __init__(self, now: datetime = _T0) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


class ApiTokenStoreContract:
    """Inherit this class in a test module, defining `store` (empty, on the
    `clock` fixture) as a pytest fixture, to run the shared ApiTokenStore
    conformance suite against a concrete implementation.
    """

    @pytest.fixture
    def clock(self) -> FakeClock:
        return FakeClock()

    def test_create_returns_a_plaintext_that_verifies(self, store: ApiTokenStore) -> None:
        token, plaintext = store.create_sync("alice", "backup script", {"stock.read"})
        assert token.token_hash == token_hash(plaintext) != plaintext
        assert (token.owner, token.name, token.scopes) == ("alice", "backup script",
                                                           frozenset({"stock.read"}))
        assert token.created_at == _T0 and token.expires_at is None and token.last_used_at is None
        verified = store.verify_sync(plaintext)
        assert verified is not None and verified.id == token.id

    def test_plaintexts_differ(self, store: ApiTokenStore) -> None:
        _, first = store.create_sync("alice", "one", set())
        _, second = store.create_sync("alice", "two", set())
        assert first != second

    def test_unknown_plaintext_is_none(self, store: ApiTokenStore) -> None:
        store.create_sync("alice", "backup script", set())
        assert store.verify_sync("not-a-token") is None

    def test_verify_records_the_last_use(self, store: ApiTokenStore, clock: FakeClock) -> None:
        token, plaintext = store.create_sync("alice", "backup script", set())
        clock.advance(minutes=5)
        assert store.verify_sync(plaintext).last_used_at == _T0 + timedelta(minutes=5)
        clock.advance(minutes=5)
        store.verify_sync(plaintext)
        [listed] = store.list_for_sync("alice")
        assert listed.last_used_at == _T0 + timedelta(minutes=10)

    def test_an_expired_token_does_not_verify(self, store: ApiTokenStore, clock: FakeClock) -> None:
        token, plaintext = store.create_sync("alice", "ci", set(),
                                             expires_at=_T0 + timedelta(days=30))
        assert token.expires_at == _T0 + timedelta(days=30)
        clock.advance(days=29)
        assert store.verify_sync(plaintext) is not None
        clock.advance(days=1)
        assert store.verify_sync(plaintext) is None
        assert [t.id for t in store.list_for_sync("alice")] == [token.id]

    def test_create_rejects_bad_input(self, store: ApiTokenStore) -> None:
        for owner, name, expires_at in (("", "n", None), ("alice", "", None),
                                        ("alice", "n", _T0), ("alice", "n", _T0 - timedelta(1))):
            with pytest.raises(ValueError):
                store.create_sync(owner, name, set(), expires_at=expires_at)
        assert store.list_for_sync("alice") == []

    def test_list_for_is_that_owners_tokens_newest_first(
        self, store: ApiTokenStore, clock: FakeClock
    ) -> None:
        older, _ = store.create_sync("alice", "older", set())
        store.create_sync("bob", "bobs", set())
        clock.advance(hours=1)
        newer, _ = store.create_sync("alice", "newer", set())
        assert [t.id for t in store.list_for_sync("alice")] == [newer.id, older.id]
        assert store.list_for_sync("carol") == []

    def test_scopes_round_trip(self, store: ApiTokenStore) -> None:
        scopes = {"stock.read", "stock.write", "audit.view"}
        _, plaintext = store.create_sync("alice", "n", scopes)
        assert store.verify_sync(plaintext).scopes == frozenset(scopes)
        assert store.list_for_sync("alice")[0].scopes == frozenset(scopes)

    def test_revoke_works_once_and_stops_the_token(self, store: ApiTokenStore) -> None:
        token, plaintext = store.create_sync("alice", "n", set())
        kept, kept_plaintext = store.create_sync("alice", "kept", set())
        assert store.revoke_sync(token.id) is True
        assert store.revoke_sync(token.id) is False
        assert store.verify_sync(plaintext) is None
        assert store.verify_sync(kept_plaintext) is not None
        assert [t.id for t in store.list_for_sync("alice")] == [kept.id]

    def test_revoke_with_an_owner_leaves_other_owners_tokens(self, store: ApiTokenStore) -> None:
        token, plaintext = store.create_sync("alice", "n", set())
        assert store.revoke_sync(token.id, owner="bob") is False
        assert store.verify_sync(plaintext) is not None
        assert store.revoke_sync(token.id, owner="alice") is True

    def test_datetimes_come_back_utc_aware(self, store: ApiTokenStore) -> None:
        _, plaintext = store.create_sync("alice", "n", set(),
                                         expires_at=datetime(2026, 2, 1, 9, 0))
        got = store.verify_sync(plaintext)
        assert got.created_at.tzinfo is not None and got.last_used_at.tzinfo is not None
        assert got.expires_at == datetime(2026, 2, 1, 9, 0, tzinfo=UTC)

    def test_async_and_sync_agree(self, store: ApiTokenStore) -> None:
        async def run():
            token, plaintext = await store.create("alice", "n", {"stock.read"})
            verified = await store.verify(plaintext)
            listed = await store.list_for("alice")
            revoked = await store.revoke(token.id, owner="alice")
            after = await store.verify(plaintext)
            return token, verified, listed, revoked, after

        token, verified, listed, revoked, after = asyncio.run(run())
        assert verified.id == token.id and verified.scopes == frozenset({"stock.read"})
        assert [t.id for t in listed] == [token.id]
        assert (revoked, after) == (True, None)
        assert store.list_for_sync("alice") == []
