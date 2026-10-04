from datetime import UTC, datetime

import pytest

from greentechhub_core.notifications import (
    KINDS,
    from_toast,
    new_notification,
    normalise_kind,
)

T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def test_new_notification_mints_an_id_and_starts_unread():
    first = new_notification("alice", "Hello", now=T0)
    second = new_notification("alice", "Hello", now=T0)
    assert len(first.id) == 32 and first.id != second.id
    assert (first.recipient, first.message, first.kind, first.category) == (
        "alice", "Hello", "info", "general")
    assert first.created_at == T0 and not first.read and first.read_at is None


def test_new_notification_defaults_its_time_to_now():
    before = datetime.now(UTC)
    note = new_notification("alice", "Now")
    assert before <= note.created_at <= datetime.now(UTC)


@pytest.mark.parametrize(("kind", "expected"), [("warn", "warning"), ("error", "danger"),
                                                *((k, k) for k in KINDS)])
def test_kinds_and_aliases(kind, expected):
    assert normalise_kind(kind) == expected
    assert new_notification("alice", "x", kind=kind).kind == expected


@pytest.mark.parametrize("kwargs", [{"recipient": ""}, {"message": ""}, {"kind": "loud"}])
def test_rejects_an_empty_recipient_or_message_and_unknown_kinds(kwargs):
    args = {"recipient": "alice", "message": "x", **kwargs}
    with pytest.raises(ValueError):
        new_notification(args.pop("recipient"), args.pop("message"), **args)


def test_to_toast_has_only_the_fields_that_are_set():
    plain = new_notification("alice", "Saved", kind="success")
    assert plain.to_toast() == {"message": "Saved", "kind": "success"}
    full = new_notification("alice", "Sync failed", kind="danger", title="ASX",
                            icon="x-octagon", action={"label": "Retry", "url": "/sync"})
    assert full.to_toast() == {"message": "Sync failed", "kind": "danger", "title": "ASX",
                               "icon": "x-octagon", "action": {"label": "Retry", "url": "/sync"}}


def test_from_toast_takes_a_detail_or_the_whole_trigger():
    detail = {"message": "Deal found", "kind": "warn", "title": "Watchlist", "icon": "tag",
              "action": {"label": "Open", "url": "/deals/1"}, "duration": 0, "variant": "solid"}
    note = from_toast("alice", detail, category="deals", now=T0)
    assert note.to_toast() == {"message": "Deal found", "kind": "warning", "title": "Watchlist",
                               "icon": "tag", "action": {"label": "Open", "url": "/deals/1"}}
    assert (note.category, note.created_at) == ("deals", T0)
    wrapped = from_toast("bob", {"showToast": {"message": "Saved", "kind": "success"}})
    assert wrapped.recipient == "bob"
    assert wrapped.to_toast() == {"message": "Saved", "kind": "success"}


def test_a_toast_without_a_message_is_rejected():
    with pytest.raises(ValueError):
        from_toast("alice", {"kind": "info"})
