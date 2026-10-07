"""background.held: take a lock for a `with` block without waiting, yield
whether it was taken, and release it on exit only if it was."""

import pytest

from greentechhub_core.background import FileLock, held


class _RecordingLock:
    """A Lock that records calls and holds names in a set."""

    def __init__(self):
        self.held: set[str] = set()
        self.calls: list[tuple[str, str, float | None]] = []

    def acquire(self, name, ttl):
        self.calls.append(("acquire", name, ttl))
        if name in self.held:
            return False
        self.held.add(name)
        return True

    def release(self, name):
        self.calls.append(("release", name, None))
        self.held.discard(name)


def test_yields_true_and_releases_after():
    lock = _RecordingLock()
    with held(lock, "job", ttl=60) as acquired:
        assert acquired and "job" in lock.held
    assert "job" not in lock.held
    assert lock.calls == [("acquire", "job", 60), ("release", "job", None)]


def test_a_second_holder_gets_false_and_releases_nothing():
    lock = _RecordingLock()
    with held(lock, "job", ttl=60) as first:
        with held(lock, "job", ttl=60) as second:
            assert first and not second
        assert "job" in lock.held  # the second didn't release the first's hold
    assert "job" not in lock.held


def test_released_on_an_exception():
    lock = _RecordingLock()
    with pytest.raises(RuntimeError), held(lock, "job", ttl=60):
        raise RuntimeError("boom")
    assert "job" not in lock.held


def test_with_a_file_lock(tmp_path):
    locks = FileLock(directory=tmp_path)
    with held(locks, "sync", ttl=5) as acquired:
        assert acquired
        with held(FileLock(directory=tmp_path), "sync", ttl=5) as other:
            assert not other  # another holder (as another worker would be)
    with held(locks, "sync", ttl=5) as again:
        assert again
