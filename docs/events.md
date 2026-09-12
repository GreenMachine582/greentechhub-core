[← Back to README](../README.md)

# 📡 Events

```python
# greentechhub_core/events/publish.py
async def publish(event: Event) -> None: ...        # logs today, then dispatches
def publish_sync(event: Event) -> None: ...          # same, for a caller with no event loop
```

v1 implementation is a structured log line per event — zero new infrastructure. The `publish`/`subscribe` interface is what matters; swapping the backend later is an internal change behind that same function signature, not a call-site change across every service.

Redis pub/sub is the next backend, once Redis exists in the stack for another reason (e.g. caching) — log-only stays the design until then.

## Defining your own events

`greentechhub_core.events.types.Event` is deliberately the *only* event type this package ships — `UserCreated`, `SyncFinished`, and so on are illustrative names, not importable classes. Each service declares its own event types in its own `<service>/events.py`, subclassing `Event`:

```python
# your_service/events.py
from dataclasses import dataclass
from greentechhub_core.events import Event

@dataclass(frozen=True, slots=True, kw_only=True)
class UserCreated(Event):
    user_id: str
    email: str
```

The `@dataclass(frozen=True, slots=True, kw_only=True)` decorator must be repeated on every subclass — dataclass decorator options aren't inherited from `Event` — in exchange the subclass gets `occurred_at` for free. This keeps one shared shape (immutable, keyword-only construction, no accidental extra attributes) without a central registry of every event type in the ecosystem.

## Publishing from sync code

`publish()` is `async`, which is fine for a subscriber but leaves a *publisher* running in sync code — Django middleware, a CLI command, a script — with nothing to await from. `publish_sync(event)` covers that: it logs the same structured line `publish()` does, then dispatches to every subscriber that is a plain sync callable. An async subscriber can't be invoked from `publish_sync()` (there's no loop to await it on), so it is skipped and logged at WARNING instead of silently dropped or run half-finished. If a subscriber needs to run from both sync and async publishers, write it as a sync callable.
