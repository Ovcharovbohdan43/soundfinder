from __future__ import annotations

import asyncio
import json
import os
import socket
import time
import uuid
from pathlib import Path


class SingleInstanceLockError(RuntimeError):
    pass


class SingleInstanceLock:
    def __init__(
        self,
        path: Path,
        *,
        stale_seconds: int,
        heartbeat_interval: int = 15,
    ) -> None:
        self._path = path
        self._stale_seconds = stale_seconds
        self._heartbeat_interval = heartbeat_interval
        self._token = uuid.uuid4().hex
        self._heartbeat_task: asyncio.Task[None] | None = None

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        for _ in range(2):
            try:
                fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._is_stale():
                    self._path.unlink(missing_ok=True)
                    continue
                raise SingleInstanceLockError(
                    f"Another bot instance is already running: {self._path}"
                )

            with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
                json.dump(self._payload(), lock_file)
            return

        raise SingleInstanceLockError(f"Could not acquire bot instance lock: {self._path}")

    def start_heartbeat(self) -> None:
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat())

    async def release(self) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        if self._owns_lock():
            self._path.unlink(missing_ok=True)

    def _payload(self) -> dict[str, str | int | float]:
        return {
            "token": self._token,
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "created_at": time.time(),
        }

    def _is_stale(self) -> bool:
        try:
            age_seconds = time.time() - self._path.stat().st_mtime
        except FileNotFoundError:
            return True
        return age_seconds > self._stale_seconds

    def _owns_lock(self) -> bool:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return False
        return payload.get("token") == self._token

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            if self._owns_lock():
                now = time.time()
                os.utime(self._path, (now, now))
