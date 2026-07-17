[← Back to README](../README.md)

# 📡 Events

```python
# greentechhub_core/events/types.py
class UserCreated(Event): ...
class SyncFinished(Event): ...

# greentechhub_core/events/publish.py
async def publish(event: Event) -> None: ...   # logs today
```

v1 implementation is a structured log line per event — zero new infrastructure. The `publish`/`subscribe` interface is what matters; swapping the backend later is an internal change behind that same function signature, not a call-site change across every service. Not urgent for v1 adoption, but worth having the shape settled before three services independently invent `on_sync_finished()` callbacks their own way.

Redis pub/sub is the next backend, once Redis exists in the stack for another reason (e.g. caching) — log-only stays the design until then.
