from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Settings
from src.infrastructure.audio_cache import AudioCache
from src.models import SearchResult
from src.services.download_service import AudioTooLargeError, DownloadService
from src.services.search_service import SearchService, SearchValidationError


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        bot_token="123:test",
        log_level="INFO",
        telegram_max_audio_mb=1,
        search_results_limit=5,
        max_query_length=20,
        max_duration_seconds=300,
        max_concurrent_downloads=2,
        max_active_downloads_per_user=1,
        data_dir=tmp_path / "data",
        tmp_dir=tmp_path / "tmp",
        cache_db_path=tmp_path / "data" / "cache.sqlite3",
        preferred_audio_codec="mp3",
        ytdlp_socket_timeout=20,
        ytdlp_cookies_file=None,
        ytdlp_cookies_b64=None,
        ytdlp_proxy=None,
        ytdlp_player_clients=("android_vr", "tv_embedded", "web_safari"),
    )


class FakeSearchClient:
    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        assert query == "artist track"
        assert limit == 5
        return [
            SearchResult("ok", "Short", "https://example.com/ok", "Artist", 180),
            SearchResult("long", "Long", "https://example.com/long", "Artist", 999),
        ]


class FakeDownloadClient:
    def __init__(self, *, size_bytes: int) -> None:
        self._size_bytes = size_bytes

    def download_audio(self, url: str, *, output_dir: Path, preferred_codec: str) -> Path:
        assert url == "https://example.com/ok"
        path = output_dir / f"audio.{preferred_codec}"
        path.write_bytes(b"x" * self._size_bytes)
        return path


async def test_search_filters_long_results(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    service = SearchService(client=FakeSearchClient(), settings=settings)  # type: ignore[arg-type]

    results = await service.search("  artist   track ")

    assert [result.source_id for result in results] == ["ok"]


async def test_search_rejects_long_query(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    service = SearchService(client=FakeSearchClient(), settings=settings)  # type: ignore[arg-type]

    with pytest.raises(SearchValidationError):
        await service.search("x" * 21)


async def test_download_rejects_files_above_telegram_limit(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    service = DownloadService(
        client=FakeDownloadClient(size_bytes=settings.telegram_max_audio_bytes + 1),  # type: ignore[arg-type]
        settings=settings,
    )

    with pytest.raises(AudioTooLargeError):
        await service.download(SearchResult("ok", "Short", "https://example.com/ok", "Artist", 180))


async def test_audio_cache_roundtrip(tmp_path: Path) -> None:
    cache = AudioCache(tmp_path / "cache.sqlite3")
    await cache.init()

    await cache.upsert(
        source_id="video-id",
        telegram_file_id="telegram-file-id",
        title="Track",
        performer="Artist",
        duration=123,
    )

    cached = await cache.get("video-id")

    assert cached is not None
    assert cached.telegram_file_id == "telegram-file-id"
    assert cached.title == "Track"
    assert cached.performer == "Artist"
    assert cached.duration == 123
