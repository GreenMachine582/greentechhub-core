"""contracts.throttle — AttemptStoreContract: shared conformance coverage for
any AttemptStore (this package's InMemoryAttemptStore and
SQLAlchemyAttemptStore, or a service's own) — see docs/testing.md.

Needs one fixture:
    store: an empty AttemptStore.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from greentechhub_core.security.throttle import AttemptStore

_T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
_WINDOW = timedelta(minutes=15)


class AttemptStoreContract:
    """Inherit this class in a test module, defining `store` (empty) as a
    pytest fixture, to run the shared AttemptStore conformance suite against
    a concrete implementation.
    """

    def test_unknown_key_is_none(self, store: AttemptStore) -> None:
        assert store.get_sync("account:nobody") is None

    def test_hits_count_up_within_the_window(self, store: AttemptStore) -> None:
        first = store.hit_sync("k", _T0, _WINDOW)
        assert (first.key, first.failures, first.window_start) == ("k", 1, _T0)
        assert first.locked_until is None
        second = store.hit_sync("k", _T0 + timedelta(minutes=5), _WINDOW)
        assert (second.failures, second.window_start) == (2, _T0)
        assert store.get_sync("k") == second

    def test_a_hit_after_the_window_starts_a_new_one(self, store: AttemptStore) -> None:
        store.hit_sync("k", _T0, _WINDOW)
        store.hit_sync("k", _T0, _WINDOW)
        later = _T0 + _WINDOW
        record = store.hit_sync("k", later, _WINDOW)
        assert (record.failures, record.window_start) == (1, later)

    def test_lock_reads_back_and_outlives_a_new_window(self, store: AttemptStore) -> None:
        store.hit_sync("k", _T0, _WINDOW)
        until = _T0 + timedelta(hours=1)
        store.lock_sync("k", until)
        assert store.get_sync("k").locked_until == until
        restarted = store.hit_sync("k", _T0 + _WINDOW, _WINDOW)
        assert (restarted.failures, restarted.locked_until) == (1, until)
        after_lock = store.hit_sync("k", until + _WINDOW, _WINDOW)
        assert after_lock.locked_until is None

    def test_lock_creates_a_missing_record(self, store: AttemptStore) -> None:
        until = _T0 + timedelta(hours=1)
        store.lock_sync("fresh", until)
        assert store.get_sync("fresh").locked_until == until

    def test_clear_removes_the_key_and_ignores_unknown_ones(self, store: AttemptStore) -> None:
        store.hit_sync("k", _T0, _WINDOW)
        store.clear_sync("k")
        store.clear_sync("never-seen")
        assert store.get_sync("k") is None

    def test_prune_deletes_only_stale_records(self, store: AttemptStore) -> None:
        store.hit_sync("old", _T0, _WINDOW)
        store.hit_sync("old-locked", _T0, _WINDOW)
        store.lock_sync("old-locked", _T0 + timedelta(days=1))
        store.hit_sync("recent", _T0 + timedelta(hours=2), _WINDOW)
        assert store.prune_sync(_T0 + timedelta(hours=1)) == 1
        assert store.get_sync("old") is None
        assert store.get_sync("old-locked") is not None
        assert store.get_sync("recent") is not None

    def test_datetimes_come_back_utc_aware(self, store: AttemptStore) -> None:
        naive = datetime(2026, 1, 1, 9, 0)
        record = store.hit_sync("k", naive, _WINDOW)
        assert record.window_start == _T0 and record.window_start.tzinfo is not None
        assert store.get_sync("k").window_start.tzinfo is not None

    def test_async_and_sync_agree(self, store: AttemptStore) -> None:
        async def run():
            first = await store.hit("a", _T0, _WINDOW)
            second = await store.hit("a", _T0, _WINDOW)
            await store.lock("a", _T0 + timedelta(hours=1))
            got = await store.get("a")
            await store.clear("b")
            await store.lock("fresh", _T0)  # a lock on a missing key creates it
            pruned = await store.prune(_T0)
            return first, second, got, pruned

        first, second, got, pruned = asyncio.run(run())
        assert (first.failures, second.failures, pruned) == (1, 2, 0)
        assert got == store.get_sync("a")
        assert got.locked_until == _T0 + timedelta(hours=1)
        assert store.get_sync("fresh").locked_until == _T0
