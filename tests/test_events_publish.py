import asyncio
import dataclasses
import json
import logging

import pytest

from greentechhub_core.events import Event, default_event_bus, publish, subscribe
from greentechhub_core.logging.setup import configure_logging


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class _UserCreated(Event):
    user_id: str


@pytest.fixture(autouse=True)
def _restore_root_logger():
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)


@pytest.fixture(autouse=True)
def _clear_default_event_bus():
    default_event_bus.clear()
    yield
    default_event_bus.clear()


def test_publish_emits_one_json_log_line_at_info(capsys):
    configure_logging("INFO")

    asyncio.run(publish(_UserCreated(user_id="u1")))

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["level"] == "INFO"


def test_publish_logs_through_the_dedicated_events_logger_name(capsys):
    configure_logging("INFO")

    asyncio.run(publish(_UserCreated(user_id="u1")))

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["logger"] == "greentechhub_core.events"


def test_publish_message_embeds_event_type_and_declared_fields(capsys):
    configure_logging("INFO")

    asyncio.run(publish(_UserCreated(user_id="u42")))

    payload = json.loads(capsys.readouterr().out.strip())
    message = json.loads(payload["message"])
    assert message["event_type"] == "_UserCreated"
    assert message["user_id"] == "u42"


def test_publish_message_embeds_occurred_at_as_isoformat(capsys):
    configure_logging("INFO")
    event = _UserCreated(user_id="u1")

    asyncio.run(publish(event))

    payload = json.loads(capsys.readouterr().out.strip())
    message = json.loads(payload["message"])
    assert message["occurred_at"] == event.occurred_at.isoformat()


def test_publish_dispatches_to_a_subscribed_sync_callback(capsys):
    configure_logging("INFO")
    received = []
    subscribe(_UserCreated, received.append)

    asyncio.run(publish(_UserCreated(user_id="u1")))

    assert len(received) == 1


def test_publish_dispatches_to_a_subscribed_async_callback(capsys):
    configure_logging("INFO")
    received = []

    async def _handler(event: _UserCreated) -> None:
        received.append(event)

    subscribe(_UserCreated, _handler)
    asyncio.run(publish(_UserCreated(user_id="u1")))

    assert len(received) == 1


def test_publish_only_dispatches_to_matching_event_type(capsys):
    configure_logging("INFO")

    @dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
    class _OtherEvent(Event):
        pass

    received = []
    subscribe(_OtherEvent, received.append)

    asyncio.run(publish(_UserCreated(user_id="u1")))

    assert received == []


def test_publish_dispatches_to_catch_all_subscribers_registered_on_event_base(capsys):
    configure_logging("INFO")
    received = []
    subscribe(Event, received.append)

    asyncio.run(publish(_UserCreated(user_id="u1")))

    assert len(received) == 1


def test_publish_continues_dispatching_when_one_subscriber_raises(capsys, caplog):
    configure_logging("INFO")
    received = []

    def _raises(_event: _UserCreated) -> None:
        raise RuntimeError("boom")

    subscribe(_UserCreated, _raises)
    subscribe(_UserCreated, received.append)

    with caplog.at_level(logging.ERROR, logger="greentechhub_core.events"):
        asyncio.run(publish(_UserCreated(user_id="u1")))

    assert len(received) == 1
    assert any(record.levelname == "ERROR" for record in caplog.records)
