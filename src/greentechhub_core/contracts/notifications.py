"""contracts.notifications — NotificationStoreContract: shared conformance
coverage for any NotificationStore (this package's InMemoryNotificationStore
and SQLAlchemyNotificationStore, or a service's own) — see docs/testing.md.

Needs one fixture:
    store: an empty NotificationStore.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from greentechhub_core.notifications import NotificationStore, new_notification

_T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def _note(recipient: str = "alice", minutes: int = 0, **kwargs):
    return new_notification(recipient, kwargs.pop("message", f"note at {minutes}"),
                            now=_T0 + timedelta(minutes=minutes), **kwargs)


class NotificationStoreContract:
    """Inherit this class in a test module, defining `store` (empty) as a
    pytest fixture, to run the shared NotificationStore conformance suite
    against a concrete implementation.
    """

    def test_unknown_recipient_has_nothing(self, store: NotificationStore) -> None:
        assert store.list_for_sync("nobody") == []
        assert store.unread_count_sync("nobody") == 0

    def test_a_notification_round_trips_every_field(self, store: NotificationStore) -> None:
        note = _note(kind="warn", title="Sync failed", icon="exclamation-triangle",
                     action={"label": "Retry", "url": "/sync"}, category="sync",
                     message="ASX sync failed: timeout")
        store.add_sync(note)
        assert store.list_for_sync("alice") == [note]

    def test_newest_first_with_a_limit(self, store: NotificationStore) -> None:
        notes = [_note(minutes=m) for m in (1, 3, 2)]
        for note in notes:
            store.add_sync(note)
        assert [n.message for n in store.list_for_sync("alice")] == [
            "note at 3", "note at 2", "note at 1"]
        assert [n.message for n in store.list_for_sync("alice", limit=2)] == [
            "note at 3", "note at 2"]

    def test_each_recipient_sees_only_their_own(self, store: NotificationStore) -> None:
        store.add_sync(_note("alice"))
        store.add_sync(_note("bob"))
        assert [n.recipient for n in store.list_for_sync("alice")] == ["alice"]
        assert store.unread_count_sync("bob") == 1

    def test_mark_read_counts_only_the_recipients_own_unread(
        self, store: NotificationStore
    ) -> None:
        mine, other, theirs = _note("alice", 1), _note("alice", 2), _note("bob", 3)
        for note in (mine, other, theirs):
            store.add_sync(note)
        at = _T0 + timedelta(hours=1)
        assert store.mark_read_sync("alice", [mine.id, theirs.id, "no-such-id"], at=at) == 1
        assert store.mark_read_sync("alice", [mine.id], at=at) == 0  # already read
        assert store.mark_read_sync("alice", [], at=at) == 0
        assert store.unread_count_sync("alice") == 1
        assert store.unread_count_sync("bob") == 1  # untouched
        read = {n.id: n for n in store.list_for_sync("alice")}[mine.id]
        assert read.read and read.read_at == at
        assert [n.id for n in store.list_for_sync("alice", unread_only=True)] == [other.id]

    def test_mark_all_read(self, store: NotificationStore) -> None:
        for minutes in (1, 2):
            store.add_sync(_note("alice", minutes))
        store.add_sync(_note("bob"))
        assert store.mark_all_read_sync("alice", at=_T0) == 2
        assert store.mark_all_read_sync("alice", at=_T0) == 0
        assert store.unread_count_sync("alice") == 0
        assert store.unread_count_sync("bob") == 1

    def test_prune_drops_only_old_read_notifications(self, store: NotificationStore) -> None:
        old_read, old_unread, new_read = _note(minutes=0), _note(minutes=1), _note(minutes=120)
        for note in (old_read, old_unread, new_read):
            store.add_sync(note)
        store.mark_read_sync("alice", [old_read.id, new_read.id], at=_T0 + timedelta(hours=3))
        assert store.prune_sync(_T0 + timedelta(hours=1)) == 1
        assert {n.id for n in store.list_for_sync("alice")} == {old_unread.id, new_read.id}

    def test_datetimes_come_back_utc_aware(self, store: NotificationStore) -> None:
        note = new_notification("alice", "naive", now=datetime(2026, 1, 1, 9, 0))
        store.add_sync(note)
        store.mark_all_read_sync("alice", at=datetime(2026, 1, 1, 10, 0))
        (got,) = store.list_for_sync("alice")
        assert got.created_at == _T0 and got.created_at.tzinfo is not None
        assert got.read_at == _T0 + timedelta(hours=1) and got.read_at.tzinfo is not None

    def test_async_and_sync_agree(self, store: NotificationStore) -> None:
        first, second = _note(minutes=1), _note(minutes=2)

        async def run():
            await store.add(first)
            await store.add(second)
            listed = await store.list_for("alice", unread_only=True, limit=10)
            count = await store.unread_count("alice")
            marked = await store.mark_read("alice", [first.id], at=_T0)
            nothing = await store.mark_read("alice", [], at=_T0)
            rest = await store.mark_all_read("alice", at=_T0)
            pruned = await store.prune(_T0 + timedelta(hours=1))
            return listed, count, marked, nothing, rest, pruned

        listed, count, marked, nothing, rest, pruned = asyncio.run(run())
        assert [n.id for n in listed] == [second.id, first.id]
        assert (count, marked, nothing, rest, pruned) == (2, 1, 0, 1, 2)
        assert store.list_for_sync("alice") == []
