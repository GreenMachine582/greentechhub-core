"""events.subscribe — EventBus: an in-process publish/subscribe registry.

No external broker exists yet (see docs/events.md); this module makes the
publish/subscribe *interface* real and exercised today, rather than a stub
that only logs, so services build against the eventual Redis-backed shape
now instead of independently inventing their own on_sync_finished()
callback convention in the meantime — swapping the backend later changes
this module's internals, not any subscribe()/publish() call site.

`EventBus` is a plain class (constructible fresh, e.g. one per test) so
tests don't leak subscriptions into each other via shared global state.
`default_event_bus` is the one shared instance events.publish.publish()
dispatches through — exposed as a module-level singleton for ergonomic
real-service use, the same "private state, public functions over it" shape
logging.context keeps its request-ID ContextVar in.
"""

import inspect
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable

from greentechhub_core.events.types import Event

type EventCallback[EventT: Event] = Callable[[EventT], Awaitable[None] | None]

_logger = logging.getLogger("greentechhub_core.events")


class EventBus:
    """An in-process registry of event subscribers, dispatched by
    `publish()`.

    Matching is by `isinstance`, not exact type equality: a callback
    subscribed on `Event` itself is a catch-all that receives every event
    ever published through this bus; one subscribed on a specific subclass
    (e.g. `UserCreated`) receives only that type (and any further subclass
    of it). There is no ordering guarantee across different registered
    types, but callbacks registered under the same type fire in
    `subscribe()` order.

    Both sync and async callbacks are supported through one `subscribe()`
    method, not two separate registration APIs — `publish()` detects which
    kind it got via `inspect.isawaitable()` on the callback's return value
    and awaits it only when needed, so a trivial counter-incrementing test
    callback doesn't need to be `async def` just to satisfy a uniform
    interface.
    """

    def __init__(self) -> None:
        self._subscribers: dict[type[Event], list[EventCallback[Event]]] = defaultdict(list)

    def subscribe[EventT: Event](
        self, event_type: type[EventT], callback: EventCallback[EventT]
    ) -> None:
        """Register `callback` to be invoked for every published event that
        is an instance of `event_type` (including subclasses).
        """
        self._subscribers[event_type].append(callback)

    def unsubscribe[EventT: Event](
        self, event_type: type[EventT], callback: EventCallback[EventT]
    ) -> None:
        """Remove `callback` from `event_type`'s registered list.

        No-ops silently if `callback` isn't currently registered under
        `event_type` — matching logging.setup.configure_logging's own
        idempotent-removal pattern (remove only if present), so a caller
        doesn't need to track its own subscription state defensively.
        """
        subscribers = self._subscribers.get(event_type)
        if subscribers and callback in subscribers:
            subscribers.remove(callback)

    async def publish(self, event: Event) -> None:
        """Dispatch `event` to every subscriber whose registered type it is
        an instance of.

        Iterates a snapshot of the registry (`list(...)` of both the
        registered-type/callback-list pairs and each callback list) so a
        subscriber that itself calls subscribe()/unsubscribe() during
        dispatch can't mutate the collection being iterated.

        A subscriber's exception (any `Exception`, not `BaseException`, so
        `KeyboardInterrupt`/`SystemExit` still propagate normally) is caught,
        logged at ERROR with a traceback, and does not stop dispatch to the
        remaining subscribers or propagate out of this method — publish's
        contract is fire-and-forget; a publisher of `UserCreated` shouldn't
        need to know or care that some unrelated subscriber's handler has a
        bug. Matching this codebase's repeated "don't let uncontrolled
        input/code break the caller" posture (DevelopmentIdentityProvider's
        tampered-token handling, verify_password's corrupt-hash handling) —
        here the "uncontrolled" part is a subscriber's own callback code,
        which this bus doesn't control.
        """
        for event_type, callbacks in list(self._subscribers.items()):
            if not isinstance(event, event_type):
                continue
            for callback in list(callbacks):
                try:
                    result = callback(event)
                    if inspect.isawaitable(result):
                        await result
                except Exception:
                    _logger.error(
                        "event subscriber raised while handling %s", type(event).__name__,
                        exc_info=True,
                    )

    def clear(self) -> None:
        """Remove every subscription. Exists for test isolation — a test
        using the shared `default_event_bus` (via the module-level
        `subscribe`/`unsubscribe`/`publish` functions) calls this in
        teardown so subscriptions don't leak into the next test.
        """
        self._subscribers.clear()


default_event_bus = EventBus()
"""The shared EventBus instance events.publish.publish() dispatches
through. Lowercase, not SCREAMING_CASE: this is a live, mutable singleton
*instance* (the same category of thing as stdlib's `logging.root`), not an
immutable constant. Left public (not underscore-prefixed) specifically so
callers — most commonly test fixtures — can call `.clear()` on it.
"""


def subscribe[EventT: Event](event_type: type[EventT], callback: EventCallback[EventT]) -> None:
    """Register `callback` on `default_event_bus` — see EventBus.subscribe."""
    default_event_bus.subscribe(event_type, callback)


def unsubscribe[EventT: Event](
    event_type: type[EventT], callback: EventCallback[EventT]
) -> None:
    """Remove `callback` from `default_event_bus` — see EventBus.unsubscribe."""
    default_event_bus.unsubscribe(event_type, callback)
