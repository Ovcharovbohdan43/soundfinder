from __future__ import annotations

from enum import StrEnum


class UserMode(StrEnum):
    MUSIC = "music"
    YOUTUBE_VIDEO = "youtube_video"


class UserModeStore:
    def __init__(self) -> None:
        self._modes: dict[int, UserMode] = {}

    def get(self, user_id: int) -> UserMode:
        return self._modes.get(user_id, UserMode.MUSIC)

    def set(self, user_id: int, mode: UserMode) -> None:
        self._modes[user_id] = mode
