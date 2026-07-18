import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from greentechhub_core.events import Event

# construction


def test_event_construction_requires_keyword_args():
    Event()
    with pytest.raises(TypeError):
        Event(datetime.now(UTC))


def test_event_is_frozen():
    event = Event()
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.occurred_at = datetime.now(UTC)


# occurred_at default


def test_occurred_at_defaults_to_a_recent_utc_datetime():
    event = Event()
    assert abs((datetime.now(UTC) - event.occurred_at).total_seconds()) < 1


def test_occurred_at_uses_a_default_factory_not_a_shared_default():
    occurred_at_field = Event.__dataclass_fields__["occurred_at"]
    assert occurred_at_field.default is dataclasses.MISSING
    assert occurred_at_field.default_factory is not dataclasses.MISSING


def test_each_instance_gets_its_own_occurred_at():
    a = Event()
    b = Event(occurred_at=a.occurred_at - timedelta(days=1))
    assert a.occurred_at != b.occurred_at


def test_explicit_occurred_at_is_honored():
    fixed = datetime(2020, 1, 1, tzinfo=UTC)
    event = Event(occurred_at=fixed)
    assert event.occurred_at == fixed


# subclassing


def test_subclassing_event_adds_fields_while_inheriting_occurred_at():
    @dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
    class _UserCreated(Event):
        user_id: str

    created = _UserCreated(user_id="u1")
    assert created.user_id == "u1"
    assert isinstance(created.occurred_at, datetime)
    assert isinstance(created, Event)
