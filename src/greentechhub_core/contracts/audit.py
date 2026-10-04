"""contracts.audit — AuditStoreContract: shared conformance coverage for any
AuditStore (this package's InMemoryAuditStore and SQLAlchemyAuditStore, or a
service's own) — see docs/testing.md.

Needs one fixture:
    store: an empty AuditStore.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from greentechhub_core.audit import AuditStore, new_entry

_T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def _entry(action="stock.archived", minutes=0, **kwargs):
    return new_entry(action, now=_T0 + timedelta(minutes=minutes), **kwargs)


class AuditStoreContract:
    """Inherit this class in a test module, defining `store` (empty) as a
    pytest fixture, to run the shared AuditStore conformance suite against a
    concrete implementation.
    """

    def test_empty(self, store: AuditStore) -> None:
        assert store.list_sync() == []

    def test_an_entry_round_trips_every_field(self, store: AuditStore) -> None:
        entry = _entry(actor="alice", target=("stock", 42), summary="Archived ASX:BHP",
                       details={"before": {"is_active": True}, "after": {"is_active": False},
                                "ids": [1, 2]})
        store.record_sync(entry)
        assert store.list_sync() == [entry]
        assert entry.target_id == "42"

    def test_system_entries_have_no_actor(self, store: AuditStore) -> None:
        entry = _entry("sync.finished", summary="ASX sync")
        store.record_sync(entry)
        (got,) = store.list_sync()
        assert got.actor is None and got.details == {}

    def test_newest_first_with_a_limit_and_a_cursor(self, store: AuditStore) -> None:
        entries = [_entry(minutes=m, summary=str(m)) for m in (1, 3, 2)]
        for entry in entries:
            store.record_sync(entry)
        assert [e.summary for e in store.list_sync()] == ["3", "2", "1"]
        assert [e.summary for e in store.list_sync(limit=2)] == ["3", "2"]
        cursor = _T0 + timedelta(minutes=2)
        assert [e.summary for e in store.list_sync(before=cursor)] == ["1"]

    def test_filters(self, store: AuditStore) -> None:
        archived = _entry("stock.archived", 1, actor="alice", target=("stock", 1))
        deleted = _entry("stock.deleted", 2, actor="bob", target=("stock", 2))
        granted = _entry("role.granted", 3, actor="alice", target=("user", "bob"))
        stockpile = _entry("stockpile.counted", 4, actor="alice")  # not a "stock." action
        for entry in (archived, deleted, granted, stockpile):
            store.record_sync(entry)

        def ids(**kwargs):
            return [e.id for e in store.list_sync(**kwargs)]

        assert ids(actor="alice") == [stockpile.id, granted.id, archived.id]
        assert ids(action="stock.deleted") == [deleted.id]
        assert ids(action="stock.") == [deleted.id, archived.id]
        assert ids(action="stock") == []  # no prefix without the dot
        assert ids(target=("stock", "1")) == [archived.id]
        assert ids(target=("stock", 2)) == [deleted.id]
        assert ids(target=("stock", None)) == [deleted.id, archived.id]
        assert ids(actor="alice", action="stock.") == [archived.id]

    def test_prune_deletes_older_entries(self, store: AuditStore) -> None:
        old, new = _entry(minutes=0), _entry(minutes=10)
        store.record_sync(old)
        store.record_sync(new)
        assert store.prune_sync(_T0 + timedelta(minutes=5)) == 1
        assert store.list_sync() == [new]

    def test_datetimes_come_back_utc_aware(self, store: AuditStore) -> None:
        store.record_sync(new_entry("stock.archived", now=datetime(2026, 1, 1, 9, 0)))
        (got,) = store.list_sync(before=datetime(2026, 1, 1, 10, 0))
        assert got.at == _T0 and got.at.tzinfo is not None

    def test_async_and_sync_agree(self, store: AuditStore) -> None:
        first, second = _entry(minutes=1, actor="alice"), _entry("role.granted", 2)

        async def run():
            await store.record(first)
            await store.record(second)
            listed = await store.list(action="stock.", limit=10)
            pruned = await store.prune(_T0 + timedelta(minutes=90))
            return listed, pruned

        listed, pruned = asyncio.run(run())
        assert [e.id for e in listed] == [first.id]
        assert pruned == 2 and store.list_sync() == []
