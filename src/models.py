from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SearchResult:
    source_id: str
    title: str
    url: str
    uploader: str | None
    duration: int | None
    thumbnail_url: str | None = None

    @property
    def display_title(self) -> str:
        if self.uploader:
            return f"{self.uploader} - {self.title}"
        return self.title


@dataclass(frozen=True)
class DownloadedAudio:
    source_id: str
    path: Path
    title: str
    performer: str | None
    duration: int | None
    size_bytes: int


@dataclass(frozen=True)
class DownloadedVideo:
    path: Path
    title: str
    duration: int | None
    width: int | None
    height: int | None
    size_bytes: int


@dataclass(frozen=True)
class DownloadedMovie:
    path: Path
    title: str
    duration: int | None
    size_bytes: int


@dataclass(frozen=True)
class CachedAudio:
    source_id: str
    telegram_file_id: str
    title: str
    performer: str | None
    duration: int | None
