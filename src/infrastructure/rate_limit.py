from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncIterator


class RateLimitExceeded(RuntimeError):
    pass


class DownloadLimiter:
    def __init__(self, *, global_limit: int, per_user_limit: int) -> None:
        self._global = asyncio.Semaphore(global_limit)
        self._per_user_limit = per_user_limit
        self._active_by_user: dict[int, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, user_id: int) -> AsyncIterator[None]:
        async with self._lock:
            if self._active_by_user[user_id] >= self._per_user_limit:
                raise RateLimitExceeded("Too many active downloads for this user")
            self._active_by_user[user_id] += 1

        await self._global.acquire()
        try:
            yield
        finally:
            self._global.release()
            async with self._lock:
                self._active_by_user[user_id] -= 1
                if self._active_by_user[user_id] <= 0:
                    self._active_by_user.pop(user_id, None)
