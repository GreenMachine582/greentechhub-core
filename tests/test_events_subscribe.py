import asyncio
import dataclasses
import logging

import pytest

from greentechhub_core.events import Event, EventBus, default_event_bus, subscribe, unsubscribe


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class _TestEvent(Event):
    value: int = 0


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class _OtherEvent(Event):
    pass


# EventBus: subscribe / dispatch


def test_subscribe_then_publish_invokes_sync_callback():
    bus = EventBus()
    received = []
    bus.subscribe(_TestEvent, received.append)

    asyncio.run(bus.publish(_TestEvent(value=1)))

    assert len(received) == 1
    assert received[0].value == 1


def test_subscribe_then_publish_invokes_and_awaits_async_callback():
    bus = EventBus()
    received = []

    async def _handler(event: _TestEvent) -> None:
        received.append(event)

    bus.subscribe(_TestEvent, _handler)
    asyncio.run(bus.publish(_TestEvent(value=2)))

    assert len(received) == 1
    assert received[0].value == 2


def test_publish_with_no_subscribers_is_a_noop():
    bus = EventBus()
    asyncio.run(bus.publish(_TestEvent()))


def test_subscribe_to_base_event_type_receives_every_subtype():
    bus = EventBus()
    received = []
    bus.subscribe(Event, received.append)

    asyncio.run(bus.publish(_TestEvent(value=3)))

    assert len(received) == 1


def test_subscribe_to_a_specific_subtype_does_not_receive_a_sibling_subtype():
    bus = EventBus()
    received = []
    bus.subscribe(_TestEvent, received.append)

    asyncio.run(bus.publish(_OtherEvent()))

    assert received == []


def test_multiple_subscribers_on_the_same_type_are_all_invoked_in_registration_order():
    bus = EventBus()
    order = []
    bus.subscribe(_TestEvent, lambda _: order.append("first"))
    bus.subscribe(_TestEvent, lambda _: order.append("second"))

    asyncio.run(bus.publish(_TestEvent()))

    assert order == ["first", "second"]


# unsubscribe


def test_unsubscribe_removes_a_callback():
    bus = EventBus()
    received = []
    callback = received.append
    bus.subscribe(_TestEvent, callback)
    bus.unsubscribe(_TestEvent, callback)

    asyncio.run(bus.publish(_TestEvent()))

    assert received == []


def test_unsubscribe_of_a_never_subscribed_callback_is_a_noop():
    bus = EventBus()
    bus.unsubscribe(_TestEvent, lambda _: None)


# exception handling


def test_exception_in_one_callback_does_not_prevent_others_from_running():
    bus = EventBus()
    received = []

    def _raises(_event: _TestEvent) -> None:
        raise RuntimeError("boom")

    bus.subscribe(_TestEvent, _raises)
    bus.subscribe(_TestEvent, received.append)

    asyncio.run(bus.publish(_TestEvent()))

    assert len(received) == 1


def test_exception_in_a_callback_is_logged_not_raised_to_the_caller(caplog):
    bus = EventBus()

    def _raises(_event: _TestEvent) -> None:
        raise RuntimeError("boom")

    bus.subscribe(_TestEvent, _raises)

    with caplog.at_level(logging.ERROR, logger="greentechhub_core.events"):
        asyncio.run(bus.publish(_TestEvent()))

    assert any(record.levelname == "ERROR" for record in caplog.records)


# clear


def test_clear_removes_all_subscriptions():
    bus = EventBus()
    received = []
    bus.subscribe(_TestEvent, received.append)
    bus.clear()

    asyncio.run(bus.publish(_TestEvent()))

    assert received == []


# default_event_bus / module-level subscribe/unsubscribe


@pytest.fixture(autouse=True)
def _clear_default_event_bus():
    default_event_bus.clear()
    yield
    default_event_bus.clear()


def test_module_level_subscribe_and_unsubscribe_delegate_to_default_event_bus():
    received = []
    subscribe(_TestEvent, received.append)

    asyncio.run(default_event_bus.publish(_TestEvent(value=9)))
    assert len(received) == 1

    unsubscribe(_TestEvent, received.append)
    asyncio.run(default_event_bus.publish(_TestEvent(value=10)))
    assert len(received) == 1
