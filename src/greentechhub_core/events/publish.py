"""events.publish — publish(): logs a structured line per event and fans the
event out to any in-process subscribers registered via events.subscribe.
v1 implementation, zero new infrastructure (see docs/events.md: "a
structured log line per event — zero new infrastructure... the
publish/subscribe interface is what matters; swapping the backend later is
an internal change").

Uses plain stdlib `logging`, not `greentechhub_core.logging`: wiring a
formatter/handler is a service's job (via logging.setup.configure_logging or
its own config), not this module's — publish() just emits through whatever
the caller already configured, keeping `events` decoupled from `logging`'s
own module boundary the same way every other top-level package here only
imports from its own submodules.

The event's structured content is embedded as a JSON string *inside* the
log record's `message`, not passed via `extra=`: reading
logging.formatter.JSONFormatter.format() shows it only ever reads
record.created/levelname/name/getMessage()/exc_info (plus the request-ID
contextvar) — it does not iterate a LogRecord's `__dict__` for arbitrary
`extra=` attributes, so `extra=` would silently produce no visible effect
in the JSON output this ecosystem's services actually emit. Embedding the
data in the message itself is a deliberate workaround for that, not an
oversight.
"""

import json
import logging
from dataclasses import asdict

from greentechhub_core.events.subscribe import default_event_bus
from greentechhub_core.events.types import Event

_logger = logging.getLogger("greentechhub_core.events")


async def publish(event: Event) -> None:
    """Log `event` as one structured INFO line, then dispatch it to every
    subscriber registered on `default_event_bus`.

    Always logs at INFO, unconditionally — this module has no concept of
    event severity; an event is a routine, expected *occurrence* being
    recorded, not an application error (contrast types.errors.
    ApplicationError, the actually-exceptional-failure path, which this
    function is unrelated to). Uses the same fixed logger name for every
    event type, rather than one logger per event type, so a log query can
    filter `logger="greentechhub_core.events"` uniformly across every
    service and every event kind — the specific event type is still
    available for finer filtering inside the message's embedded JSON.

    Logs before dispatching to subscribers: the event's occurrence is
    durably recorded before any arbitrary subscriber code runs, which
    EventBus.publish tolerates raising from without losing that record.

    `async` even though the logging call itself is a blocking write:
    EventBus.publish may need to await async subscriber callbacks, and that
    await point has to live somewhere in this call chain.
    """
    _logger.info(_render(event))
    await default_event_bus.publish(event)


def _render(event: Event) -> str:
    """Render `event` as a single-line JSON string: its concrete type name,
    `occurred_at` as an ISO 8601 string, and every other declared field
    flattened alongside them.

    Uses `dataclasses.asdict` (recursive) rather than walking
    `__dataclass_fields__` manually — every Event subclass is guaranteed to
    be a dataclass by convention (see types.Event's subclassing contract),
    so asdict's recursive dict conversion is always applicable, including
    for a subclass field that itself happens to be a nested dataclass.

    `json.dumps(..., default=str)`: a subclass field of a type json can't
    natively serialize (e.g. Decimal, UUID) degrades to `str()` rather than
    raising — publish() logging an event should not itself crash on a
    plausible-but-unhandled field type.
    """
    fields = asdict(event)
    occurred_at = fields.pop("occurred_at")
    payload = {
        "event_type": type(event).__name__,
        "occurred_at": occurred_at.isoformat(),
        **fields,
    }
    return json.dumps(payload, default=str)
