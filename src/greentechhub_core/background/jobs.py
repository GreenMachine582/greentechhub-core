"""background.jobs — in-process background jobs with progress, cooperative
pause/resume/cancel and a result: what a "Scan this folder" or "Build the
library" button starts and a progress bar polls.

- Job: one run's record (state, progress, result or error, timestamps).
- JobStore: where Job records live; InMemoryJobStore is the reference one.
- JobContext: handed to the job function, which reports progress and calls
  checkpoint() between units of work (where pause and cancel take effect).
- JobRunner: starts a job function as an asyncio task (a coroutine
  function) or in a worker thread (a plain function), keeps its live state,
  and publishes JobFinished on the EventBus when it ends.

    async def scan(ctx: JobContext) -> dict:
        files = list_files(folder)
        for n, path in enumerate(files, 1):
            await ctx.checkpoint()          # pauses here; raises JobCancelled
            index(path)
            ctx.progress(n, len(files), message=path.name)
        return {"files": len(files)}

    job = await runner.start("scan", scan, label="Scan D:\\Music", unique=True)

Jobs run in this process: a restart loses the ones still running (their
last saved state stays in a persistent store). Pause and cancel are
cooperative: they take effect at the job's next checkpoint(), and a
coroutine job is also cancelled at its next await.
"""

import asyncio
import inspect
import logging
import threading
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from greentechhub_core.background.locks import Lock
from greentechhub_core.events import Event, EventBus, default_event_bus

_logger = logging.getLogger(__name__)


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def finished(self) -> bool:
        return self in (JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class Job:
    """One background job run.

    `done`/`total` are the progress counts (`total` None while unknown: an
    indeterminate bar), `message` what it's doing now. `result` is the job
    function's returned mapping once it succeeded; `error` is set when it
    failed. `owner` is the subject who started it, or None for the system.
    """

    id: str
    kind: str
    label: str
    owner: str | None = None
    state: JobState = JobState.QUEUED
    done: int = 0
    total: int | None = None
    message: str = ""
    result: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def active(self) -> bool:
        """Queued, running or paused: not finished yet."""
        return not self.state.finished

    @property
    def fraction(self) -> float | None:
        """done / total, clamped to 0..1; None while the total is unknown."""
        if not self.total:
            return None
        return min(max(self.done / self.total, 0.0), 1.0)


def new_job(kind: str, *, label: str | None = None, owner: str | None = None,
            now: datetime | None = None) -> Job:
    """A queued Job with a fresh id."""
    return Job(id=uuid.uuid4().hex, kind=kind, label=label or kind, owner=owner,
               created_at=_aware(now) if now is not None else datetime.now(UTC))


@dataclass(frozen=True, slots=True, kw_only=True)
class JobFinished(Event):
    """Published when a job succeeds, fails or is cancelled: `job.state` says
    which. A service subscribes to notify someone or record it."""

    job: Job


class JobCancelled(Exception):
    """Raised by JobContext.checkpoint() once the job was cancelled. A job
    function lets it propagate (cleaning up on the way, if it must)."""


class JobAlreadyRunning(Exception):
    """JobRunner.start(..., unique=True) found an active job of the same kind."""

    def __init__(self, job: Job | None) -> None:
        super().__init__("a job of this kind is already running")
        self.job = job


# ── store ────────────────────────────────────────────────────────────────


class JobStore(Protocol):
    """Structural contract for a job store. Each operation comes as an async
    method plus a `_sync` twin, like NotificationStore.

    Semantics every implementation keeps (JobStoreContract asserts them):
      - `save` inserts or replaces the job with that id.
      - `get` returns it, or None.
      - `jobs` returns them newest first (by created_at, then id), at most
        `limit`, filtered by `kind`, by `owner`, and by `active` (True: not
        finished; False: finished; None: either).
      - `prune(before)` deletes finished jobs created before `before` and
        returns how many; active ones are never pruned.
    Datetimes come back UTC-aware.
    """

    async def save(self, job: Job) -> None: ...

    def save_sync(self, job: Job) -> None: ...

    async def get(self, job_id: str) -> Job | None: ...

    def get_sync(self, job_id: str) -> Job | None: ...

    async def jobs(self, *, kind: str | None = None, owner: str | None = None,
                   active: bool | None = None, limit: int = 50) -> list[Job]: ...

    def jobs_sync(self, *, kind: str | None = None, owner: str | None = None,
                  active: bool | None = None, limit: int = 50) -> list[Job]: ...

    async def prune(self, before: datetime) -> int: ...

    def prune_sync(self, before: datetime) -> int: ...


def newest_first(jobs: Any) -> list[Job]:
    """`jobs` sorted the way JobStore.jobs returns them."""
    return sorted(jobs, key=lambda j: (_aware(j.created_at), j.id), reverse=True)


def _matches(job: Job, kind: str | None, owner: str | None, active: bool | None) -> bool:
    return ((kind is None or job.kind == kind) and (owner is None or job.owner == owner)
            and (active is None or job.active == active))


class InMemoryJobStore:
    """A process-local JobStore — a dict of id → Job behind a lock. Nothing
    persists across restarts. The async methods delegate to the sync ones."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}

    def save_sync(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job

    def get_sync(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def jobs_sync(self, *, kind: str | None = None, owner: str | None = None,
                  active: bool | None = None, limit: int = 50) -> list[Job]:
        with self._lock:
            jobs = [j for j in self._jobs.values() if _matches(j, kind, owner, active)]
        return newest_first(jobs)[:limit]

    def prune_sync(self, before: datetime) -> int:
        before = _aware(before)
        with self._lock:
            stale = [k for k, j in self._jobs.items()
                     if not j.active and _aware(j.created_at) < before]
            for key in stale:
                del self._jobs[key]
            return len(stale)

    async def save(self, job: Job) -> None:
        self.save_sync(job)

    async def get(self, job_id: str) -> Job | None:
        return self.get_sync(job_id)

    async def jobs(self, *, kind: str | None = None, owner: str | None = None,
                   active: bool | None = None, limit: int = 50) -> list[Job]:
        return self.jobs_sync(kind=kind, owner=owner, active=active, limit=limit)

    async def prune(self, before: datetime) -> int:
        return self.prune_sync(before)


# ── runner ───────────────────────────────────────────────────────────────

JobResult = Mapping[str, Any] | None
JobFunction = Callable[["JobContext"], JobResult | Awaitable[JobResult]]


@dataclass(eq=False)
class _Live:
    job: Job
    fn: JobFunction
    run: threading.Event = field(default_factory=threading.Event)  # clear while paused
    cancel: threading.Event = field(default_factory=threading.Event)
    task: asyncio.Task[None] | None = None
    lock_name: str | None = None

    def __post_init__(self) -> None:
        self.run.set()


class JobContext:
    """What a job function gets: report progress, and call checkpoint()
    (async jobs) or checkpoint_sync() (thread jobs) between units of work.
    Every method is safe to call from the job's worker thread."""

    def __init__(self, runner: "JobRunner", live: _Live) -> None:
        self._runner = runner
        self._live = live

    @property
    def job_id(self) -> str:
        return self._live.job.id

    @property
    def cancelled(self) -> bool:
        """True once cancel() was asked for; checkpoint() will raise."""
        return self._live.cancel.is_set()

    def progress(self, done: int | None = None, total: int | None = None,
                 message: str | None = None) -> None:
        """Update the counts and/or message; only the arguments given change.
        Cheap: it updates the live view and isn't saved to the store until the
        next state change."""
        changes: dict[str, Any] = {}
        if done is not None:
            changes["done"] = done
        if total is not None:
            changes["total"] = total
        if message is not None:
            changes["message"] = message
        if changes:
            self._runner._update(self._live, persist=False, **changes)

    def checkpoint_sync(self) -> None:
        """Raise JobCancelled if the job was cancelled; block while it's
        paused. For a job running in a worker thread."""
        live = self._live
        if live.cancel.is_set():
            raise JobCancelled
        live.run.wait()
        if live.cancel.is_set():
            raise JobCancelled

    async def checkpoint(self) -> None:
        """checkpoint_sync() for a coroutine job: waits without blocking the
        event loop."""
        live = self._live
        while not live.run.is_set() and not live.cancel.is_set():
            await asyncio.sleep(0.05)
        if live.cancel.is_set():
            raise JobCancelled


class JobRunner:
    """Runs jobs in this process and keeps their state in `store`.

    `start` runs a coroutine function as an asyncio task and a plain
    function in a worker thread (asyncio.to_thread), passing a JobContext.
    The function's returned mapping becomes the job's `result`; an exception
    fails it (its message becomes `error`); JobCancelled cancels it.

    `get`/`jobs` answer from the live view while a job runs, so progress is
    current without a store write per update; the store is written on each
    state change (queued, running, paused, resumed, finished).

    `lock` (optional, e.g. a FileLock) makes `unique=True` hold across
    processes too: each unique kind takes the lock "job-<kind>" while it runs.
    """

    def __init__(self, store: JobStore, *, event_bus: EventBus | None = None,
                 lock: Lock | None = None, lock_ttl: float = 6 * 60 * 60) -> None:
        self.store = store
        self._bus = event_bus if event_bus is not None else default_event_bus
        self._lock = lock
        self._lock_ttl = lock_ttl
        self._guard = threading.Lock()
        self._live: dict[str, _Live] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: int | None = None
        self._pending: set[asyncio.Task[None]] = set()
        self._save_lock: asyncio.Lock | None = None

    # -- starting ----------------------------------------------------------

    async def start(self, kind: str, fn: JobFunction, *, label: str | None = None,
                    owner: str | None = None, unique: bool = False) -> Job:
        """Start `fn(ctx)` as a job of `kind` and return it (already running).

        `unique=True` raises JobAlreadyRunning while another job of `kind`
        is active (in this runner, or holding the lock in another process).
        """
        self._bind_loop()
        lock_name = None
        with self._guard:
            if unique:
                running = next((lv.job for lv in self._live.values()
                                if lv.job.kind == kind and lv.job.active), None)
                if running is not None:
                    raise JobAlreadyRunning(running)
                if self._lock is not None:
                    lock_name = f"job-{kind}"
                    if not self._lock.acquire(lock_name, self._lock_ttl):
                        raise JobAlreadyRunning(None)
            live = _Live(job=new_job(kind, label=label, owner=owner), fn=fn,
                         lock_name=lock_name)
            self._live[live.job.id] = live
        await self._save(live.job.id)
        live.task = asyncio.get_running_loop().create_task(self._run(live))
        return live.job

    async def _run(self, live: _Live) -> None:
        ctx = JobContext(self, live)
        self._update(live, state=JobState.RUNNING, started_at=datetime.now(UTC))
        outcome: dict[str, Any]
        try:
            if live.cancel.is_set():  # cancelled before it got going
                raise JobCancelled
            if inspect.iscoroutinefunction(live.fn):
                result = await live.fn(ctx)
            else:
                result = await asyncio.to_thread(live.fn, ctx)
                if inspect.isawaitable(result):
                    result = await result
        except (JobCancelled, asyncio.CancelledError):
            outcome = {"state": JobState.CANCELLED}
        except Exception as exc:
            _logger.exception("job %s (%s) failed", live.job.id, live.job.kind)
            outcome = {"state": JobState.FAILED, "error": str(exc) or type(exc).__name__}
        else:
            outcome = {"state": JobState.SUCCEEDED, "result": dict(result or {})}
        finally:
            if live.lock_name is not None and self._lock is not None:
                self._lock.release(live.lock_name)
        self._update(live, persist=False, finished_at=datetime.now(UTC), **outcome)
        await self._save(live.job.id)
        with self._guard:
            self._live.pop(live.job.id, None)
        await self._bus.publish(JobFinished(job=live.job))

    # -- controlling -------------------------------------------------------

    def pause(self, job_id: str) -> Job | None:
        """Ask a running job to pause at its next checkpoint. Returns the job,
        or None when it isn't active in this runner."""
        live = self._get_live(job_id)
        if live is None:
            return None
        if live.job.state in (JobState.QUEUED, JobState.RUNNING):
            live.run.clear()
            self._update(live, state=JobState.PAUSED)
        return live.job

    def resume(self, job_id: str) -> Job | None:
        """Let a paused job carry on. Returns the job, or None."""
        live = self._get_live(job_id)
        if live is None:
            return None
        if live.job.state is JobState.PAUSED:
            self._update(live, state=JobState.RUNNING)
            live.run.set()
        return live.job

    def cancel(self, job_id: str) -> Job | None:
        """Cancel a job: it stops at its next checkpoint (a coroutine job also
        at its next await) and ends cancelled. Returns the job, or None."""
        live = self._get_live(job_id)
        if live is None:
            return None
        live.cancel.set()
        live.run.set()
        # A task cancelled before its first step never runs _run's body (so
        # would never finish): until it has started, the flag alone does it.
        started = live.job.started_at is not None
        if started and live.task is not None and inspect.iscoroutinefunction(live.fn):
            live.task.cancel()
        return live.job

    async def wait(self, job_id: str, timeout: float | None = None) -> Job | None:
        """Wait for a job of this runner to finish and return its final state
        (or its current one if `timeout` runs out)."""
        live = self._get_live(job_id)
        if live is not None and live.task is not None:
            await asyncio.wait({live.task}, timeout=timeout)
        return await self.get(job_id)

    async def shutdown(self, timeout: float = 5.0) -> None:
        """Cancel every active job and wait up to `timeout` for them to end.
        A thread job that never reaches a checkpoint keeps its thread."""
        with self._guard:
            lives = list(self._live.values())
        for live in lives:
            self.cancel(live.job.id)
        tasks = {live.task for live in lives if live.task is not None}
        if tasks:
            await asyncio.wait(tasks, timeout=timeout)
        if self._pending:
            await asyncio.wait(set(self._pending), timeout=timeout)

    # -- reading -----------------------------------------------------------

    async def get(self, job_id: str) -> Job | None:
        """The job's current state: live while it runs, else from the store."""
        live = self._get_live(job_id)
        if live is not None:
            return live.job
        return await self.store.get(job_id)

    async def jobs(self, *, kind: str | None = None, owner: str | None = None,
                   active: bool | None = None, limit: int = 50) -> list[Job]:
        """Like JobStore.jobs, with running jobs' live progress."""
        jobs = {j.id: j for j in await self.store.jobs(kind=kind, owner=owner, active=active,
                                                         limit=limit)}
        with self._guard:
            for live in self._live.values():
                if live.job.id in jobs or _matches(live.job, kind, owner, active):
                    jobs[live.job.id] = live.job
        return newest_first(j for j in jobs.values()
                            if _matches(j, kind, owner, active))[:limit]

    # -- internals ---------------------------------------------------------

    def _bind_loop(self) -> None:
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._loop = loop
            self._loop_thread = threading.get_ident()
            self._save_lock = asyncio.Lock()

    def _get_live(self, job_id: str) -> _Live | None:
        with self._guard:
            return self._live.get(job_id)

    def _update(self, live: _Live, *, persist: bool = True, **changes: Any) -> None:
        with self._guard:
            live.job = replace(live.job, **changes)
        if persist:
            self._schedule_save(live.job.id)

    def _schedule_save(self, job_id: str) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        if threading.get_ident() == self._loop_thread:
            self._spawn_save(job_id)
        else:
            loop.call_soon_threadsafe(self._spawn_save, job_id)

    def _spawn_save(self, job_id: str) -> None:
        task = asyncio.get_running_loop().create_task(self._save(job_id))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _save(self, job_id: str) -> None:
        # Always the latest snapshot, one save at a time: saves that land out
        # of order can't overwrite a newer state with an older one.
        assert self._save_lock is not None
        async with self._save_lock:
            live = self._get_live(job_id)
            if live is None:
                return
            try:
                await self.store.save(live.job)
            except Exception:
                _logger.exception("job %s: saving its state failed", job_id)
