from __future__ import annotations

import os
import time

import pytest

from src.infrastructure.single_instance import SingleInstanceLock, SingleInstanceLockError


async def test_single_instance_lock_rejects_second_owner(tmp_path) -> None:
    lock_path = tmp_path / "telegram_polling.lock"
    first = SingleInstanceLock(lock_path, stale_seconds=120)
    second = SingleInstanceLock(lock_path, stale_seconds=120)

    first.acquire()
    try:
        with pytest.raises(SingleInstanceLockError):
            second.acquire()
    finally:
        await first.release()

    assert not lock_path.exists()


async def test_single_instance_lock_replaces_stale_file(tmp_path) -> None:
    lock_path = tmp_path / "telegram_polling.lock"
    lock_path.write_text("stale", encoding="utf-8")
    stale_time = time.time() - 300
    os.utime(lock_path, (stale_time, stale_time))

    lock = SingleInstanceLock(lock_path, stale_seconds=120)
    lock.acquire()
    try:
        assert lock_path.exists()
    finally:
        await lock.release()
