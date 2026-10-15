"""background.held: take a lock for a `with` block without waiting, yield
whether it was taken, and release it on exit only if it was."""

import re

import pytest

from greentechhub_core.background import FileLock, file_lock_for, held, held_lock, lock_name, locks


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


class _Settings:
    def __init__(self, directory):
        self._directory = str(directory)

    def lock_directory(self) -> str:
        return self._directory


def test_held_lock_refuses_a_second_caller_until_released(tmp_path):
    settings = _Settings(tmp_path)
    with held_lock(settings, "market-sync-ASX", ttl=60) as first:
        with held_lock(settings, "market-sync-ASX", ttl=60) as second:
            assert first and not second
    with held_lock(settings, "market-sync-ASX", ttl=60) as again:
        assert again


def test_held_lock_releases_when_the_block_raises(tmp_path):
    settings = _Settings(tmp_path)
    with pytest.raises(RuntimeError):
        with held_lock(settings, "sync", ttl=60) as acquired:
            assert acquired
            raise RuntimeError("sync failed")
    with held_lock(settings, "sync", ttl=60) as acquired:
        assert acquired


def test_held_lock_passes_the_ttl_to_held(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(locks, "held", lambda lock, name, ttl: calls.append((lock, name, ttl)))
    held_lock(_Settings(tmp_path), "sync", ttl=900)
    assert calls == [(file_lock_for(tmp_path), "sync", 900)]


def test_file_lock_for_caches_one_lock_per_directory(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert file_lock_for(a) is file_lock_for(str(a)) is file_lock_for(a / ".." / "a")
    assert file_lock_for(a) is not file_lock_for(b)
    assert a.is_dir()


@pytest.mark.parametrize("name", ["", "a/b", "../escape", "has space", "back\slash"])
def test_held_lock_rejects_a_name_that_isnt_filename_safe(tmp_path, name):
    with pytest.raises(ValueError, match="lock_name"):
        held_lock(_Settings(tmp_path), name, ttl=60)


def test_lock_name_keeps_the_prefix_and_hashes_the_parts():
    name = lock_name("email-sync", "alice@example.com")
    assert re.fullmatch(r"email-sync-[0-9a-f]{16}", name)
    assert name == lock_name("email-sync", "alice@example.com")
    assert name != lock_name("email-sync", "bob@example.com")
    assert lock_name("job", "a", "bc") != lock_name("job", "ab", "c")
    assert lock_name("market-sync-ASX") == "market-sync-ASX"


def test_lock_name_output_is_usable_by_held_lock(tmp_path):
    with held_lock(_Settings(tmp_path), lock_name("sync", "../../etc/passwd"), ttl=60) as acquired:
        assert acquired
    assert [p.parent for p in tmp_path.iterdir()] == [tmp_path]


@pytest.mark.parametrize("prefix", ["", "a/b", "has space"])
def test_lock_name_rejects_an_unsafe_prefix(prefix):
    with pytest.raises(ValueError, match="prefix"):
        lock_name(prefix, "x")
