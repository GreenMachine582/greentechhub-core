"""contracts.jobs — JobStoreContract: shared conformance coverage for any
JobStore (this package's InMemoryJobStore, or a service's own) — see
docs/testing.md.

Needs one fixture:
    store: an empty JobStore.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from greentechhub_core.background import JobState, JobStore, new_job

_T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def _job(kind: str = "scan", minutes: int = 0, **changes):
    job = new_job(kind, owner=changes.pop("owner", None), now=_T0 + timedelta(minutes=minutes))
    return replace(job, **changes) if changes else job


class JobStoreContract:
    """Inherit this class in a test module, defining `store` (empty) as a
    pytest fixture, to run the shared JobStore conformance suite against a
    concrete implementation.
    """

    def test_unknown_id_is_none(self, store: JobStore) -> None:
        assert store.get_sync("nope") is None
        assert store.jobs_sync() == []

    def test_a_job_round_trips_every_field(self, store: JobStore) -> None:
        job = _job(owner="alice", state=JobState.SUCCEEDED, done=3, total=4, message="last.mp3",
                   result={"files": 4, "badges": [["4 files", "good"]]}, error=None,
                   started_at=_T0, finished_at=_T0 + timedelta(seconds=5))
        store.save_sync(job)
        assert store.get_sync(job.id) == job

    def test_save_replaces(self, store: JobStore) -> None:
        job = _job()
        store.save_sync(job)
        store.save_sync(replace(job, state=JobState.RUNNING, done=1))
        got = store.get_sync(job.id)
        assert got is not None and got.state is JobState.RUNNING and got.done == 1
        assert len(store.jobs_sync()) == 1

    def test_newest_first_with_a_limit(self, store: JobStore) -> None:
        jobs = [_job(minutes=m, label=f"at {m}") for m in (1, 3, 2)]
        for job in jobs:
            store.save_sync(job)
        assert [j.label for j in store.jobs_sync()] == ["at 3", "at 2", "at 1"]
        assert [j.label for j in store.jobs_sync(limit=2)] == ["at 3", "at 2"]

    def test_filters(self, store: JobStore) -> None:
        scan = _job("scan", owner="alice", state=JobState.RUNNING)
        build = _job("build", minutes=1, state=JobState.FAILED, error="boom")
        for job in (scan, build):
            store.save_sync(job)
        assert store.jobs_sync(kind="build") == [build]
        assert store.jobs_sync(owner="alice") == [scan]
        assert store.jobs_sync(active=True) == [scan]
        assert store.jobs_sync(active=False) == [build]

    def test_prune_removes_only_old_finished_jobs(self, store: JobStore) -> None:
        old_done = _job(minutes=0, state=JobState.SUCCEEDED)
        old_running = _job(minutes=1, state=JobState.RUNNING)
        new_done = _job(minutes=60, state=JobState.CANCELLED)
        for job in (old_done, old_running, new_done):
            store.save_sync(job)
        assert store.prune_sync(_T0 + timedelta(minutes=30)) == 1
        assert {j.id for j in store.jobs_sync()} == {old_running.id, new_done.id}

    def test_datetimes_come_back_aware(self, store: JobStore) -> None:
        job = _job(started_at=_T0)
        store.save_sync(job)
        got = store.get_sync(job.id)
        assert got is not None and got.created_at.tzinfo is not None
        assert got.started_at is not None and got.started_at.tzinfo is not None
