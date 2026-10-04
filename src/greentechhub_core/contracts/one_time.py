"""contracts.one_time — TokenStoreContract: shared conformance coverage for
any TokenStore (this package's InMemoryTokenStore and SQLAlchemyTokenStore,
or a service's own) — see docs/testing.md.

Needs one fixture:
    store: an empty TokenStore.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from greentechhub_core.security.one_time import TokenRecord, TokenStore

_T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def _record(token_hash: str = "a" * 64, *, subject: str = "alice", purpose: str = "password_reset",
            hours: int = 1, used_at: datetime | None = None) -> TokenRecord:
    return TokenRecord(token_hash=token_hash, purpose=purpose, subject=subject, created_at=_T0,
                       expires_at=_T0 + timedelta(hours=hours), used_at=used_at)


class TokenStoreContract:
    """Inherit this class in a test module, defining `store` (empty) as a
    pytest fixture, to run the shared TokenStore conformance suite against a
    concrete implementation.
    """

    def test_unknown_hash_is_none(self, store: TokenStore) -> None:
        assert store.get_sync("0" * 64) is None

    def test_a_record_round_trips(self, store: TokenStore) -> None:
        record = _record()
        store.add_sync(record)
        assert store.get_sync(record.token_hash) == record

    def test_use_succeeds_once(self, store: TokenStore) -> None:
        record = _record()
        store.add_sync(record)
        at = _T0 + timedelta(minutes=5)
        assert store.use_sync(record.token_hash, at) is True
        assert store.use_sync(record.token_hash, at) is False
        assert store.use_sync("0" * 64, at) is False
        assert store.get_sync(record.token_hash).used_at == at

    def test_revoke_deletes_only_that_subjects_unused_tokens_for_the_purpose(
        self, store: TokenStore
    ) -> None:
        keep_used = _record("1" * 64, used_at=_T0)
        doomed = (_record("2" * 64), _record("3" * 64))
        other_purpose = _record("4" * 64, purpose="email_verification")
        other_subject = _record("5" * 64, subject="bob")
        for record in (keep_used, *doomed, other_purpose, other_subject):
            store.add_sync(record)
        assert store.revoke_sync("alice", "password_reset") == 2
        assert store.revoke_sync("alice", "password_reset") == 0
        for record in doomed:
            assert store.get_sync(record.token_hash) is None
        for record in (keep_used, other_purpose, other_subject):
            assert store.get_sync(record.token_hash) == record

    def test_prune_deletes_only_expired_or_used_before_the_cutoff(
        self, store: TokenStore
    ) -> None:
        expired = _record("1" * 64, hours=1)
        used = _record("2" * 64, hours=48, used_at=_T0 + timedelta(minutes=1))
        live = _record("3" * 64, hours=48)
        used_late = _record("4" * 64, hours=48, used_at=_T0 + timedelta(hours=5))
        for record in (expired, used, live, used_late):
            store.add_sync(record)
        assert store.prune_sync(_T0 + timedelta(hours=2)) == 2
        assert store.get_sync(expired.token_hash) is None
        assert store.get_sync(used.token_hash) is None
        assert store.get_sync(live.token_hash) == live
        assert store.get_sync(used_late.token_hash) == used_late

    def test_datetimes_come_back_utc_aware(self, store: TokenStore) -> None:
        naive = datetime(2026, 1, 1, 9, 0)
        store.add_sync(TokenRecord(token_hash="a" * 64, purpose="p", subject="s", created_at=naive,
                                   expires_at=naive + timedelta(hours=1)))
        store.use_sync("a" * 64, naive)
        got = store.get_sync("a" * 64)
        assert got.created_at == _T0 and got.created_at.tzinfo is not None
        assert got.expires_at.tzinfo is not None and got.used_at == _T0

    def test_async_and_sync_agree(self, store: TokenStore) -> None:
        first, second = _record("1" * 64), _record("2" * 64)

        async def run():
            await store.add(first)
            await store.add(second)
            got = await store.get(first.token_hash)
            used = await store.use(first.token_hash, _T0)
            again = await store.use(first.token_hash, _T0)
            revoked = await store.revoke("alice", "password_reset")
            pruned = await store.prune(_T0 + timedelta(hours=2))
            return got, used, again, revoked, pruned

        got, used, again, revoked, pruned = asyncio.run(run())
        assert got == first
        assert (used, again, revoked, pruned) == (True, False, 1, 1)
        assert store.get_sync(first.token_hash) is None
        assert store.get_sync(second.token_hash) is None
