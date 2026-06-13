from __future__ import annotations

from src.infrastructure.user_mode_store import UserMode, UserModeStore


def test_user_mode_defaults_to_music() -> None:
    store = UserModeStore()

    assert store.get(100) == UserMode.MUSIC


def test_user_mode_can_switch_to_youtube_video() -> None:
    store = UserModeStore()

    store.set(100, UserMode.YOUTUBE_VIDEO)

    assert store.get(100) == UserMode.YOUTUBE_VIDEO
    assert store.get(200) == UserMode.MUSIC
