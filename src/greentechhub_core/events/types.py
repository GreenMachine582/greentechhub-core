"""events.types — Event: the base type every concrete domain event
subclasses. See docs/events.md.

Deliberately does not define `UserCreated`/`SyncFinished` — those are
docs/events.md's own illustrative examples, not members this package
provides. Same reasoning permissions.catalogue already applies to
"portfolio.view"/"import.run": each service owns its own domain events, this
module only supplies the shared shape every one of them must carry. A
module-level registry of "every event type this package knows about" would
recreate exactly the kind of duplication that reasoning warns against.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    """Base type for a domain event — the one field every concrete event
    (defined by a consuming service, not this package) inherits.

    Fields:
        occurred_at: UTC timestamp of when the event occurred. Defaults to
            "now" via `field(default_factory=...)`, not a bare
            `= datetime.now(UTC)` — a dataclass field's plain default
            expression is evaluated once, at class-definition time, which
            would freeze every `Event` ever constructed at this module's
            import time; `default_factory` evaluates per instance instead,
            matching `RawAuthContext.headers`'s own `field(default_factory=
            dict)` use for the same "don't share one default across
            instances" reason.

    No `name`/`type` string field: `type(event).__name__` already identifies
    a concrete event unambiguously (see events.publish._render), so a second,
    independently-settable string field would only risk drifting from the
    class it's attached to. No generic `payload: dict[str, Any]` field
    either — a concrete event declares its own typed fields directly (e.g.
    `class UserCreated(Event): user_id: str`), the same typed-vocabulary-over
    -untyped-bag preference permissions.catalogue.Permission applies to a
    validated string over an arbitrary one. A service wanting a freeform bag
    can still declare that field itself; this base class just doesn't
    presuppose it.

    Subclassing contract: every subclass must repeat
    `@dataclass(frozen=True, slots=True, kw_only=True)` itself — Python
    dataclass decorator options aren't inherited — and gets `occurred_at`
    for free via inheritance, e.g.:

        @dataclass(frozen=True, slots=True, kw_only=True)
        class UserCreated(Event):
            user_id: str
            email: str
    """

    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
