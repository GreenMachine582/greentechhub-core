"""background.locks — Lock protocol and FileLock: the one background/*
primitive worth shipping before a real scheduler exists (see TODO.md) — a
scheduler-less service still needs "don't let two replicas run the same
periodic job at once," and a lock has no framework or scheduler dependency
of its own.

background/scheduler.py and background/tasks.py are deliberately not built
yet: zero consumers ask for a scheduler today (BottleBot has its own
scraper cadence, PyFinBot is greenfield, Market Watch doesn't exist), and
APScheduler's own 4.x line has been pre-release with a shifting API for an
extended period — wrapping either version now risks a rewrite before this
package has a single real consumer to validate the wrapper against. Land
them once a consumer actually needs ≥2 scheduled jobs, not on a fixed
version.
"""

import os
import sys
import time
from pathlib import Path
from typing import Protocol, TextIO


class Lock(Protocol):
    """Structural contract every lock backend implements. A typing.Protocol,
    matching every other adapter-swappable interface in this package
    (IdentityProvider, FeatureFlagProvider) — nothing needs
    isinstance(x, Lock).
    """

    def acquire(self, name: str, ttl: float) -> bool:
        """Attempt to acquire the named lock, returning immediately (never
        blocking/retrying) — True if acquired, False if another holder
        currently has it. Matches the actual use case: a scheduled job
        either gets the lock and runs, or skips this cycle — it has no
        reason to sit around waiting for another replica to finish.

        `ttl` is the lock's intended maximum validity once acquired. It's
        part of this Protocol because a future distributed backend (a
        Redis-backed Lock, landing once Redis is deployed for some other
        reason — same trigger as events.publish's Redis backend) has no
        OS-level "the holder crashed, release it" primitive and must use an
        expiry to recover from a dead holder — see FileLock's own docstring
        for why a single-host, OS-advisory-lock-backed implementation
        doesn't actually need to act on it for its own correctness.
        """
        ...

    def release(self, name: str) -> None:
        """Release the named lock. No-ops if this instance doesn't
        currently hold it — matching this package's established idempotent
        -removal precedent (events.subscribe.EventBus.unsubscribe).
        """
        ...


class FileLock:
    """Single-host Lock backed by a real OS-level advisory file lock
    (fcntl.flock on POSIX, msvcrt.locking on Windows) — "enough for the
    homelab" per TODO.md: every replica of a service runs on the one host
    this lock file lives on. A distributed (multi-host) Redis-backed Lock
    is deferred until Redis is actually deployed for some other reason,
    matching docs/events.md's identical gating for the Redis event-bus
    backend.

    Why a real OS-level advisory lock rather than a plain "does this file
    exist" check: the OS releases an advisory lock automatically the
    instant the holding process exits, *crashed or not* — there is no
    window where a dead holder's lock is left permanently stuck, unlike a
    plain lock-file-existence check, which would need its own manual
    staleness/expiry recovery to survive a crash.

    `ttl` is accepted (satisfying the shared Lock protocol — see its own
    docstring) but doesn't gate this implementation's acquire/release
    correctness: because the OS already guarantees release-on-exit, there
    is no "stale lock from a dead holder" state here for a ttl-based expiry
    to recover from — that problem is specific to backends (Redis) with no
    such OS guarantee. It's still written into the lock file's content
    (informational — a human debugging a held lock can see how long it was
    meant to last and which pid took it) so switching backends later
    doesn't silently drop information a caller may already depend on
    seeing.
    """

    def __init__(self, *, directory: str | Path) -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._held: dict[str, TextIO] = {}

    def acquire(self, name: str, ttl: float) -> bool:
        path = self._directory / f"{name}.lock"
        handle = open(path, "a+")

        # msvcrt.locking requires at least one byte already present to lock
        # byte 0 of an empty file; harmless on POSIX, where fcntl.flock
        # locks the whole file regardless of content.
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write("0")
            handle.flush()

        if not _try_lock(handle):
            handle.close()
            return False

        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()} expires_at={time.time() + ttl}")
        handle.flush()
        self._held[name] = handle
        return True

    def release(self, name: str) -> None:
        handle = self._held.pop(name, None)
        if handle is None:
            return
        _unlock(handle)
        handle.close()


if sys.platform == "win32":
    import msvcrt

    def _try_lock(handle: TextIO) -> bool:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def _unlock(handle: TextIO) -> None:
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass

else:
    import fcntl

    def _try_lock(handle: TextIO) -> bool:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _unlock(handle: TextIO) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
