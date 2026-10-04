from datetime import UTC, datetime

import pytest

from greentechhub_core.audit import REDACTED, check_action, new_entry, scrub

T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def test_new_entry_mints_an_id_and_a_time():
    first = new_entry("stock.archived", actor="alice", target=("stock", 7), summary="Archived",
                      now=T0)
    second = new_entry("stock.archived")
    assert len(first.id) == 32 and first.id != second.id
    assert (first.at, first.actor) == (T0, "alice")
    assert (first.target_type, first.target_id) == ("stock", "7")
    assert second.at.tzinfo is not None and second.actor is None


@pytest.mark.parametrize("action", ["stock.archived", "role.granted", "sync.asx_market.finished"])
def test_good_actions(action):
    assert check_action(action) == action


@pytest.mark.parametrize("action", ["archived", "Stock.Archived", "stock archived", "stock.", ".x",
                                    ""])
def test_bad_actions(action):
    with pytest.raises(ValueError):
        new_entry(action)


@pytest.mark.parametrize("target", [("", 1), ("stock", None), ("stock", "")])
def test_a_target_needs_a_type_and_an_id(target):
    with pytest.raises(ValueError):
        new_entry("stock.archived", target=target)


def test_details_must_be_json():
    with pytest.raises(ValueError):
        new_entry("stock.archived", details={"when": T0})


def test_credential_like_details_are_scrubbed_at_any_depth():
    entry = new_entry("user.updated", details={
        "Password": "hunter2",
        "user": {"name": "bob", "api_key": "abc", "tokens": ["x"]},
        "changes": [{"field": "email", "new_password_hash": "$2b$..."}],
        "count": 3,
    })
    assert entry.details == {
        "Password": REDACTED,
        "user": {"name": "bob", "api_key": REDACTED, "tokens": REDACTED},
        "changes": [{"field": "email", "new_password_hash": REDACTED}],
        "count": 3,
    }


def test_scrub_leaves_plain_values_alone():
    assert scrub("text") == "text"
    assert scrub([1, ("a", {"secret": 1})]) == [1, ["a", {"secret": REDACTED}]]
