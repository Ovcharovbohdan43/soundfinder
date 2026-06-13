from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import aiosqlite


@dataclass(frozen=True)
class BotUser:
    user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    first_seen_at: int
    last_seen_at: int
    is_blocked: bool


@dataclass(frozen=True)
class BotStats:
    total_users: int
    active_today: int
    active_7d: int
    events_today: dict[str, int]
    events_total: dict[str, int]


class AnalyticsStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    first_seen_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL,
                    is_blocked INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    event_type TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_bot_events_created_at ON bot_events(created_at)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_bot_events_type_created ON bot_events(event_type, created_at)"
            )
            await db.commit()

    async def upsert_user(
        self,
        *,
        user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> None:
        now = int(time.time())
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO bot_users (
                    user_id, username, first_name, last_name, first_seen_at, last_seen_at, is_blocked
                )
                VALUES (?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    last_seen_at = excluded.last_seen_at,
                    is_blocked = 0
                """,
                (user_id, username, first_name, last_name, now, now),
            )
            await db.commit()

    async def mark_blocked(self, user_id: int) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE bot_users SET is_blocked = 1 WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()

    async def record_event(self, event_type: str, *, user_id: int | None = None) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO bot_events (user_id, event_type, created_at) VALUES (?, ?, ?)",
                (user_id, event_type, int(time.time())),
            )
            await db.commit()

    async def broadcast_user_ids(self) -> list[int]:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT user_id FROM bot_users WHERE is_blocked = 0 ORDER BY user_id"
            )
            rows = await cursor.fetchall()
        return [int(row[0]) for row in rows]

    async def stats(self) -> BotStats:
        now = int(time.time())
        today_start = now - (now % 86400)
        week_start = now - 7 * 86400
        async with aiosqlite.connect(self._db_path) as db:
            total_users = await self._fetch_scalar(db, "SELECT COUNT(*) FROM bot_users")
            active_today = await self._fetch_scalar(
                db,
                "SELECT COUNT(*) FROM bot_users WHERE last_seen_at >= ?",
                (today_start,),
            )
            active_7d = await self._fetch_scalar(
                db,
                "SELECT COUNT(*) FROM bot_users WHERE last_seen_at >= ?",
                (week_start,),
            )
            events_today = await self._event_counts(db, since=today_start)
            events_total = await self._event_counts(db, since=None)
        return BotStats(
            total_users=total_users,
            active_today=active_today,
            active_7d=active_7d,
            events_today=events_today,
            events_total=events_total,
        )

    @staticmethod
    async def _fetch_scalar(
        db: aiosqlite.Connection,
        query: str,
        params: tuple[object, ...] = (),
    ) -> int:
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        return int(row[0] if row is not None else 0)

    @staticmethod
    async def _event_counts(
        db: aiosqlite.Connection,
        *,
        since: int | None,
    ) -> dict[str, int]:
        if since is None:
            cursor = await db.execute(
                "SELECT event_type, COUNT(*) FROM bot_events GROUP BY event_type"
            )
        else:
            cursor = await db.execute(
                """
                SELECT event_type, COUNT(*)
                FROM bot_events
                WHERE created_at >= ?
                GROUP BY event_type
                """,
                (since,),
            )
        rows = await cursor.fetchall()
        return {str(row[0]): int(row[1]) for row in rows}
