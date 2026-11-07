"""Unit and concurrency tests for atomic experiment locking."""

import concurrent.futures
import os
from pathlib import Path

import pytest

from phoenix_eval.core.exceptions import ExperimentError
from phoenix_eval.experiment.runner import FileLock


def test_file_lock_lifecycle_creates_and_releases(tmp_path: Path) -> None:
    """Verify standard file lock acquire and release lifecycle."""
    lock_path = tmp_path / ".experiment.lock"
    assert not lock_path.exists()

    with FileLock(lock_path) as lock:
        assert lock._acquired is True
        assert lock_path.exists()
        content = lock_path.read_text(encoding="utf-8")
        assert f"pid={os.getpid()}" in content
        assert "timestamp=" in content

    assert not lock_path.exists()


def test_file_lock_second_acquire_fails(tmp_path: Path) -> None:
    """Verify that attempting to acquire an already held lock raises ExperimentError with owner info."""
    lock_path = tmp_path / ".experiment.lock"
    lock1 = FileLock(lock_path)
    lock1.acquire()

    lock2 = FileLock(lock_path)
    with pytest.raises(ExperimentError, match="Another experiment runner is currently executing"):
        lock2.acquire()

    # Verify stale lock recovery instructions are present in exception message
    try:
        lock2.acquire()
    except ExperimentError as exc:
        assert "Stale Lock Recovery" in str(exc)
        assert str(os.getpid()) in str(exc)

    lock1.release()
    assert not lock_path.exists()


def test_file_lock_concurrency_race(tmp_path: Path) -> None:
    """Verify atomic concurrency: among multiple concurrent threads, exactly one acquires the lock."""
    lock_path = tmp_path / ".experiment.lock"
    num_threads = 10
    successes = 0
    failures = 0
    acquired_locks: list[FileLock] = []

    def try_lock() -> bool:
        lock = FileLock(lock_path)
        try:
            lock.acquire()
            acquired_locks.append(lock)
            return True
        except ExperimentError:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(try_lock) for _ in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            if f.result():
                successes += 1
            else:
                failures += 1

    assert successes == 1
    assert failures == num_threads - 1

    # Cleanup the 1 acquired lock
    for lk in acquired_locks:
        lk.release()
    assert not lock_path.exists()


def test_file_lock_pid_mismatch_skips_deletion(tmp_path: Path) -> None:
    """Verify that release() does not delete a lock file owned by a different PID."""
    lock_path = tmp_path / ".experiment.lock"
    # Create fake lock file owned by PID 999999
    lock_path.write_text("pid=999999\ntimestamp=2026-01-01T00:00:00Z\n", encoding="utf-8")

    lock = FileLock(lock_path)
    lock._acquired = True  # Simulate acquired state
    lock.release()

    # The file must NOT be deleted because PID did not match
    assert lock_path.exists()
    content = lock_path.read_text(encoding="utf-8")
    assert "pid=999999" in content
