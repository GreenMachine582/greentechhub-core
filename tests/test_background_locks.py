from greentechhub_core.background import FileLock

_TTL = 30.0


def test_acquire_returns_true_when_lock_is_free(tmp_path):
    lock = FileLock(directory=tmp_path)
    assert lock.acquire("job", _TTL) is True


def test_second_instance_cannot_acquire_a_lock_already_held(tmp_path):
    first = FileLock(directory=tmp_path)
    second = FileLock(directory=tmp_path)

    assert first.acquire("job", _TTL) is True
    assert second.acquire("job", _TTL) is False


def test_release_allows_a_different_instance_to_then_acquire(tmp_path):
    first = FileLock(directory=tmp_path)
    second = FileLock(directory=tmp_path)

    assert first.acquire("job", _TTL) is True
    first.release("job")
    assert second.acquire("job", _TTL) is True


def test_release_is_a_no_op_for_a_name_never_acquired(tmp_path):
    lock = FileLock(directory=tmp_path)
    lock.release("never-acquired")  # must not raise


def test_locks_on_different_names_are_independent(tmp_path):
    first = FileLock(directory=tmp_path)
    second = FileLock(directory=tmp_path)

    assert first.acquire("job-a", _TTL) is True
    assert second.acquire("job-b", _TTL) is True


def test_constructor_creates_the_directory_if_missing(tmp_path):
    directory = tmp_path / "locks" / "nested"
    FileLock(directory=directory)
    assert directory.is_dir()


def test_lock_file_content_records_pid_and_expiry(tmp_path):
    # Read after release, not while held: on Windows, msvcrt's byte-range
    # lock is mandatory, not just advisory — a separate handle can't even
    # read the locked byte while another handle holds it. Reading after
    # release also matches the realistic case: inspecting an orphaned lock
    # file from outside the process that took it.
    lock = FileLock(directory=tmp_path)
    lock.acquire("job", _TTL)
    lock.release("job")

    content = (tmp_path / "job.lock").read_text()
    assert "pid=" in content
    assert "expires_at=" in content
