"""background.jobs: JobRunner runs coroutine and thread jobs with progress,
cooperative pause/resume/cancel, a result or an error, and JobFinished."""

import asyncio
import threading
import time

import pytest

from greentechhub_core.background import (
    InMemoryJobStore,
    JobAlreadyRunning,
    JobCancelled,
    JobContext,
    JobFinished,
    JobRunner,
    JobState,
)
from greentechhub_core.contracts.jobs import JobStoreContract
from greentechhub_core.events import EventBus


class TestInMemoryJobStoreContract(JobStoreContract):
    @pytest.fixture
    def store(self) -> InMemoryJobStore:
        return InMemoryJobStore()


def _runner(**kwargs) -> tuple[JobRunner, list[JobFinished]]:
    bus = EventBus()
    finished: list[JobFinished] = []
    bus.subscribe(JobFinished, finished.append)
    return JobRunner(InMemoryJobStore(), event_bus=bus, **kwargs), finished


async def _until(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("timed out")
        await asyncio.sleep(0.01)


def test_a_coroutine_job_reports_progress_and_succeeds():
    async def main():
        runner, finished = _runner()

        async def work(ctx: JobContext):
            for n in range(1, 4):
                await ctx.checkpoint()
                ctx.progress(n, 3, message=f"item {n}")
            return {"files": 3}

        job = await runner.start("scan", work, label="Scan music", owner="alice")
        assert job.state is JobState.QUEUED and job.label == "Scan music"
        done = await runner.wait(job.id)
        assert done is not None
        assert done.state is JobState.SUCCEEDED
        assert (done.done, done.total, done.message) == (3, 3, "item 3")
        assert done.result == {"files": 3} and done.fraction == 1.0
        assert done.started_at is not None and done.finished_at is not None
        assert await runner.store.get(job.id) == done
        assert [e.job for e in finished] == [done]

    asyncio.run(main())


def test_a_thread_job_runs_off_the_event_loop():
    async def main():
        runner, _ = _runner()
        loop_thread = threading.get_ident()
        seen: list[int] = []

        def work(ctx: JobContext):
            seen.append(threading.get_ident())
            ctx.checkpoint_sync()
            ctx.progress(1, 1)
            return {"ok": True}

        job = await runner.start("build", work)
        done = await runner.wait(job.id)
        assert done is not None and done.state is JobState.SUCCEEDED
        assert done.result == {"ok": True} and seen and seen[0] != loop_thread

    asyncio.run(main())


def test_live_progress_is_visible_while_running():
    async def main():
        runner, _ = _runner()
        release = asyncio.Event()

        async def work(ctx: JobContext):
            ctx.progress(0, 10, message="starting")
            ctx.progress(4)
            await release.wait()

        job = await runner.start("scan", work)
        await _until(lambda: runner._live[job.id].job.done == 4)
        live = await runner.get(job.id)
        assert live is not None
        assert (live.state, live.done, live.total, live.message) == (
            JobState.RUNNING, 4, 10, "starting")
        assert live.fraction == 0.4 and live.active
        assert [j.id for j in await runner.jobs(active=True)] == [job.id]
        release.set()
        await runner.wait(job.id)

    asyncio.run(main())


def test_pause_then_resume_a_thread_job():
    async def main():
        runner, _ = _runner()
        steps: list[int] = []
        go = threading.Event()

        def work(ctx: JobContext):
            for n in range(3):
                go.wait()
                ctx.checkpoint_sync()
                steps.append(n)
            return {"steps": len(steps)}

        job = await runner.start("apply", work)
        await _until(lambda: runner._live[job.id].job.state is JobState.RUNNING)
        paused = runner.pause(job.id)
        assert paused is not None and paused.state is JobState.PAUSED
        go.set()
        await asyncio.sleep(0.1)
        assert steps == []  # held at the checkpoint
        assert (await runner.store.get(job.id)).state is JobState.PAUSED
        resumed = runner.resume(job.id)
        assert resumed is not None and resumed.state is JobState.RUNNING
        done = await runner.wait(job.id)
        assert done is not None and done.state is JobState.SUCCEEDED and steps == [0, 1, 2]

    asyncio.run(main())


def test_cancel_a_paused_coroutine_job():
    async def main():
        runner, finished = _runner()
        reached = asyncio.Event()

        async def work(ctx: JobContext):
            while True:
                reached.set()
                await ctx.checkpoint()
                await asyncio.sleep(0.01)

        job = await runner.start("scan", work)
        await reached.wait()
        runner.pause(job.id)
        runner.cancel(job.id)
        done = await runner.wait(job.id, timeout=5)
        assert done is not None and done.state is JobState.CANCELLED
        assert finished[0].job.state is JobState.CANCELLED

    asyncio.run(main())


def test_cancel_a_thread_job_at_its_checkpoint():
    async def main():
        runner, _ = _runner()
        started = threading.Event()

        def work(ctx: JobContext):
            started.set()
            while True:
                ctx.checkpoint_sync()
                time.sleep(0.01)

        job = await runner.start("scan", work)
        await asyncio.to_thread(started.wait)
        runner.cancel(job.id)
        done = await runner.wait(job.id, timeout=5)
        assert done is not None and done.state is JobState.CANCELLED

    asyncio.run(main())


def test_cancel_before_the_job_starts():
    async def main():
        runner, _ = _runner()
        ran: list[bool] = []

        async def work(ctx: JobContext):
            ran.append(True)

        job = await runner.start("scan", work)
        runner.cancel(job.id)
        done = await runner.wait(job.id, timeout=5)
        assert done is not None and done.state is JobState.CANCELLED and ran == []

    asyncio.run(main())


def test_a_failure_records_the_error():
    async def main():
        runner, finished = _runner()

        def work(ctx: JobContext):
            raise OSError("D:\\ is not ready")

        job = await runner.start("scan", work)
        done = await runner.wait(job.id)
        assert done is not None and done.state is JobState.FAILED
        assert done.error == "D:\\ is not ready" and done.result == {}
        assert finished[0].job.state is JobState.FAILED

    asyncio.run(main())


def test_unique_refuses_a_second_active_job_of_the_kind():
    async def main():
        runner, _ = _runner()
        release = asyncio.Event()

        async def work(ctx: JobContext):
            await release.wait()

        first = await runner.start("scan", work, unique=True)
        with pytest.raises(JobAlreadyRunning) as raised:
            await runner.start("scan", work, unique=True)
        assert raised.value.job is not None and raised.value.job.id == first.id
        other = await runner.start("build", work, unique=True)  # another kind is fine
        release.set()
        await runner.wait(first.id)
        await runner.wait(other.id)
        again = await runner.start("scan", work, unique=True)  # finished: allowed again
        await runner.wait(again.id)

    asyncio.run(main())


class _FakeLock:
    def __init__(self) -> None:
        self.held: set[str] = set()

    def acquire(self, name: str, ttl: float) -> bool:
        if name in self.held:
            return False
        self.held.add(name)
        return True

    def release(self, name: str) -> None:
        self.held.discard(name)


def test_unique_takes_the_lock_while_running():
    async def main():
        lock = _FakeLock()
        runner, _ = _runner(lock=lock)
        elsewhere = JobRunner(InMemoryJobStore(), event_bus=EventBus(), lock=lock)
        release = asyncio.Event()

        async def work(ctx: JobContext):
            await release.wait()

        job = await runner.start("scan", work, unique=True)
        assert lock.held == {"job-scan"}
        with pytest.raises(JobAlreadyRunning) as raised:
            await elsewhere.start("scan", work, unique=True)
        assert raised.value.job is None
        release.set()
        await runner.wait(job.id)
        assert lock.held == set()

    asyncio.run(main())


def test_controls_on_an_unknown_or_finished_job_return_none():
    async def main():
        runner, _ = _runner()

        async def work(ctx: JobContext):
            return None

        job = await runner.start("scan", work)
        await runner.wait(job.id)
        assert runner.pause(job.id) is None
        assert runner.resume(job.id) is None
        assert runner.cancel("missing") is None
        done = await runner.get(job.id)
        assert done is not None and done.result == {}

    asyncio.run(main())


def test_shutdown_cancels_active_jobs():
    async def main():
        runner, _ = _runner()

        async def forever(ctx: JobContext):
            while True:
                await ctx.checkpoint()
                await asyncio.sleep(0.01)

        def forever_in_a_thread(ctx: JobContext):
            while True:
                ctx.checkpoint_sync()
                time.sleep(0.01)

        a = await runner.start("a", forever)
        b = await runner.start("b", forever_in_a_thread)
        await asyncio.sleep(0.05)
        await runner.shutdown()
        assert (await runner.get(a.id)).state is JobState.CANCELLED
        assert (await runner.get(b.id)).state is JobState.CANCELLED

    asyncio.run(main())


def test_job_cancelled_is_an_exception_a_job_can_clean_up_on():
    assert issubclass(JobCancelled, Exception)
