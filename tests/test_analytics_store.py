from __future__ import annotations

from pathlib import Path

from src.infrastructure.analytics_store import AnalyticsStore


async def test_analytics_store_tracks_users_events_and_broadcast_targets(tmp_path: Path) -> None:
    store = AnalyticsStore(tmp_path / "cache.sqlite3")
    await store.init()

    await store.upsert_user(
        user_id=1,
        username="alice",
        first_name="Alice",
        last_name=None,
    )
    await store.upsert_user(
        user_id=2,
        username="bob",
        first_name="Bob",
        last_name=None,
    )
    await store.record_event("music_search", user_id=1)
    await store.record_event("audio_sent", user_id=1)
    await store.mark_blocked(2)

    stats = await store.stats()

    assert stats.total_users == 2
    assert stats.active_today == 2
    assert stats.events_today["music_search"] == 1
    assert stats.events_total["audio_sent"] == 1
    assert await store.broadcast_user_ids() == [1]
