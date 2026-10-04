"""throttle — login throttling: count failed attempts per key and lock a key
out for a while once it reaches a limit, so a password can't be guessed
forever — see docs/modules.md#login-throttling.

Two layers, like permissions' grants:
  - AttemptStore: where the counts live. InMemoryAttemptStore here (tests,
    single-process tools, the reference AttemptStoreContract is checked
    against); SQLAlchemyAttemptStore in greentechhub_core.sqlalchemy for a
    service's own database.
  - LoginThrottle: the policy — a fixed window of `window` in which
    `max_failures` failures lock the key for `lockout`.

Keys are plain strings. A login form throttles by account AND by client
(`account_key(username)`, `client_key(ip)`), so neither one guesser trying
many accounts nor many clients trying one account gets unlimited tries;
other forms (register, password reset) can use their own prefixes.

Framework-free: showing a generic error and a Retry-After header is the
adapter's job (greentechhub-fastapi's login views).
"""

import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol


def aware(value: datetime) -> datetime:
    """`value` as a UTC-aware datetime; a naive one is taken to be UTC (some
    databases, SQLite among them, drop the zone on the way back)."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class Attempts:
    """One key's failed-attempt record.

    Fields:
        key: what is throttled, e.g. "account:alice" or "client:203.0.113.7".
        failures: failures counted in the current window.
        window_start: when the current window began (UTC).
        locked_until: when a lockout ends (UTC), or None when not locked.
    """

    key: str
    failures: int
    window_start: datetime
    locked_until: datetime | None = None

    def locked(self, now: datetime) -> bool:
        return self.locked_until is not None and aware(self.locked_until) > aware(now)


def next_attempts(current: Attempts | None, key: str, now: datetime, window: timedelta) -> Attempts:
    """The record after one more failure at `now` — the rule every
    AttemptStore.hit follows: a missing key, or one whose window has run
    out, starts a new window at one failure (keeping a lock that hasn't
    ended); otherwise the count goes up by one."""
    now = aware(now)
    if current is None or aware(current.window_start) + window <= now:
        lock = current.locked_until if current is not None and current.locked(now) else None
        return Attempts(key=key, failures=1, window_start=now, locked_until=lock)
    return replace(current, failures=current.failures + 1)


def is_stale(record: Attempts, before: datetime) -> bool:
    """Whether `record` can be pruned: its window started before `before` and
    any lock it had ended before then too."""
    before = aware(before)
    lock_over = record.locked_until is None or aware(record.locked_until) < before
    return aware(record.window_start) < before and lock_over


class AttemptStore(Protocol):
    """Structural contract for a failed-attempt store. Each operation comes
    as an async method plus a `_sync` twin, like GrantStore.

    Semantics every implementation keeps (AttemptStoreContract asserts them):
      - `get` of an unknown key is None.
      - `hit` counts one failure atomically, following `next_attempts`, and
        returns the new record.
      - `lock` sets `locked_until` (creating the record if needed).
      - `clear` of an unknown key is a no-op.
      - `prune(before)` deletes every record `is_stale` says can go and
        returns how many it deleted.
    Datetimes are returned UTC-aware.
    """

    async def get(self, key: str) -> Attempts | None: ...

    def get_sync(self, key: str) -> Attempts | None: ...

    async def hit(self, key: str, now: datetime, window: timedelta) -> Attempts: ...

    def hit_sync(self, key: str, now: datetime, window: timedelta) -> Attempts: ...

    async def lock(self, key: str, until: datetime) -> None: ...

    def lock_sync(self, key: str, until: datetime) -> None: ...

    async def clear(self, key: str) -> None: ...

    def clear_sync(self, key: str) -> None: ...

    async def prune(self, before: datetime) -> int: ...

    def prune_sync(self, before: datetime) -> int: ...


class InMemoryAttemptStore:
    """A process-local AttemptStore — a dict of key → Attempts behind a lock,
    safe to share across threads. Nothing persists across restarts, and each
    process counts on its own: a service running several workers wants the
    database-backed store. The async methods delegate to the sync ones."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, Attempts] = {}

    def get_sync(self, key: str) -> Attempts | None:
        with self._lock:
            return self._records.get(key)

    def hit_sync(self, key: str, now: datetime, window: timedelta) -> Attempts:
        with self._lock:
            record = next_attempts(self._records.get(key), key, now, window)
            self._records[key] = record
            return record

    def lock_sync(self, key: str, until: datetime) -> None:
        with self._lock:
            current = self._records.get(key)
            if current is None:
                current = Attempts(key=key, failures=0, window_start=aware(until))
            self._records[key] = replace(current, locked_until=aware(until))

    def clear_sync(self, key: str) -> None:
        with self._lock:
            self._records.pop(key, None)

    def prune_sync(self, before: datetime) -> int:
        with self._lock:
            stale = [key for key, record in self._records.items() if is_stale(record, before)]
            for key in stale:
                del self._records[key]
            return len(stale)

    async def get(self, key: str) -> Attempts | None:
        return self.get_sync(key)

    async def hit(self, key: str, now: datetime, window: timedelta) -> Attempts:
        return self.hit_sync(key, now, window)

    async def lock(self, key: str, until: datetime) -> None:
        self.lock_sync(key, until)

    async def clear(self, key: str) -> None:
        self.clear_sync(key)

    async def prune(self, before: datetime) -> int:
        return self.prune_sync(before)


@dataclass(frozen=True, slots=True, kw_only=True)
class ThrottleStatus:
    """The answer for a set of keys.

    Fields:
        allowed: False while any key is locked out.
        retry_after: how long until every lock has ended, or None if allowed.
        failures: the highest failure count among the keys.
    """

    allowed: bool
    retry_after: timedelta | None = None
    failures: int = 0


def account_key(username: str) -> str:
    """The throttle key for an account: case and surrounding spaces don't
    make a new key, so "Alice " and "alice" share one count."""
    return "account:" + username.strip().casefold()


def client_key(address: str) -> str:
    """The throttle key for a client, e.g. its IP address (after trusted-proxy
    resolution, so a spoofed X-Forwarded-For can't pick a fresh key)."""
    return "client:" + address.strip()


def _status(records: Iterable[Attempts | None], now: datetime) -> ThrottleStatus:
    present = [r for r in records if r is not None]
    failures = max((r.failures for r in present), default=0)
    locks = [aware(r.locked_until) for r in present if r.locked_until is not None and r.locked(now)]
    if not locks:
        return ThrottleStatus(allowed=True, failures=failures)
    return ThrottleStatus(allowed=False, retry_after=max(locks) - aware(now), failures=failures)


class LoginThrottle:
    """Fixed-window lockout over an AttemptStore.

    `max_failures` failures for a key within `window` of its first failure
    lock that key for `lockout`. A failure after the lock ends but still in
    the same window locks it again straight away, so a guesser gets one try
    per lockout until the window runs out. A success clears the key.

    Every method takes one or more keys and answers for the most restrictive
    of them. Each comes as an async method plus a `_sync` twin.

    Args:
        store: where the counts live.
        max_failures: failures that trigger a lockout (default 5).
        window: how long failures keep counting from the first (default 15 min).
        lockout: how long a key stays locked (default 15 min).
        clock: returns the current time; tests pass a fake one.
    """

    def __init__(
        self,
        store: AttemptStore,
        *,
        max_failures: int = 5,
        window: timedelta = timedelta(minutes=15),
        lockout: timedelta = timedelta(minutes=15),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if max_failures < 1:
            raise ValueError(f"max_failures must be at least 1, got {max_failures!r}")
        if window <= timedelta(0) or lockout <= timedelta(0):
            raise ValueError("window and lockout must be positive")
        self._store = store
        self.max_failures = max_failures
        self.window = window
        self.lockout = lockout
        self._clock = clock

    def _now(self) -> datetime:
        return aware(self._clock())

    def _locks(self, record: Attempts, now: datetime) -> bool:
        return record.failures >= self.max_failures and not record.locked(now)

    # sync

    def check_sync(self, *keys: str) -> ThrottleStatus:
        """Whether an attempt may go ahead now (call before checking the password)."""
        return _status((self._store.get_sync(k) for k in keys), self._now())

    def record_failure_sync(self, *keys: str) -> ThrottleStatus:
        """Count a failed attempt against every key; returns the status after
        it, so the attempt that trips a lockout already reports it."""
        now = self._now()
        records = []
        for key in keys:
            record = self._store.hit_sync(key, now, self.window)
            if self._locks(record, now):
                self._store.lock_sync(key, now + self.lockout)
                record = replace(record, locked_until=now + self.lockout)
            records.append(record)
        return _status(records, now)

    def record_success_sync(self, *keys: str) -> None:
        """Forget the keys' failures, e.g. the account after a correct password."""
        for key in keys:
            self._store.clear_sync(key)

    def prune_sync(self) -> int:
        """Delete records no window or lockout still needs; returns how many."""
        return self._store.prune_sync(self._now() - max(self.window, self.lockout))

    # async

    async def check(self, *keys: str) -> ThrottleStatus:
        return _status([await self._store.get(k) for k in keys], self._now())

    async def record_failure(self, *keys: str) -> ThrottleStatus:
        now = self._now()
        records = []
        for key in keys:
            record = await self._store.hit(key, now, self.window)
            if self._locks(record, now):
                await self._store.lock(key, now + self.lockout)
                record = replace(record, locked_until=now + self.lockout)
            records.append(record)
        return _status(records, now)

    async def record_success(self, *keys: str) -> None:
        for key in keys:
            await self._store.clear(key)

    async def prune(self) -> int:
        return await self._store.prune(self._now() - max(self.window, self.lockout))
