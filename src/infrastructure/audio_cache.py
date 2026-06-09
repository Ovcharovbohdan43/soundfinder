from __future__ import annotations

import time
from pathlib import Path

import aiosqlite

from src.models import CachedAudio


class AudioCache:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS audio_cache (
                    source_id TEXT PRIMARY KEY,
                    telegram_file_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    performer TEXT,
                    duration INTEGER,
                    created_at INTEGER NOT NULL
                )
                """
            )
            await db.commit()

    async def get(self, source_id: str) -> CachedAudio | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT source_id, telegram_file_id, title, performer, duration
                FROM audio_cache
                WHERE source_id = ?
                """,
                (source_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return CachedAudio(
            source_id=row["source_id"],
            telegram_file_id=row["telegram_file_id"],
            title=row["title"],
            performer=row["performer"],
            duration=row["duration"],
        )

    async def upsert(
        self,
        *,
        source_id: str,
        telegram_file_id: str,
        title: str,
        performer: str | None,
        duration: int | None,
    ) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO audio_cache (
                    source_id, telegram_file_id, title, performer, duration, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    telegram_file_id = excluded.telegram_file_id,
                    title = excluded.title,
                    performer = excluded.performer,
                    duration = excluded.duration,
                    created_at = excluded.created_at
                """,
                (source_id, telegram_file_id, title, performer, duration, int(time.time())),
            )
            await db.commit()
