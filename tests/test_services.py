from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Settings
from src.infrastructure.audio_cache import AudioCache
from src.infrastructure.imusic_client import IMusicError, IMusicTrack
from src.models import SearchResult
from src.services.download_service import AudioTooLargeError, DownloadService
from src.services.search_service import SearchProviderError, SearchService, SearchValidationError


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        bot_token="123:test",
        log_level="INFO",
        telegram_max_audio_mb=1,
        search_results_limit=5,
        search_results_page_size=5,
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
        ytdlp_cookies_source="none",
        ytdlp_proxy=None,
        ytdlp_player_clients=("android_vr", "tv_embedded", "web_safari"),
        imusic_fallback_enabled=True,
        imusic_base_url="https://two.imusic.fm/",
        imusic_timeout=12,
        youtube_search_enabled=False,
        telegram_single_instance_lock=True,
        telegram_lock_stale_seconds=120,
        telegram_polling_timeout=10,
        telegram_tasks_concurrency_limit=20,
        direct_telegram_audio_url_enabled=True,
    )


class FakeSearchClient:
    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        assert query == "artist track"
        assert limit == 5
        return [
            SearchResult("ok", "Short", "https://example.com/ok", "Artist", 180),
            SearchResult("long", "Long", "https://example.com/long", "Artist", 999),
        ]


class FailingSearchClient:
    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        raise AssertionError("YouTube search should not be used when iMusic returns results")


class FakeDownloadClient:
    def __init__(self, *, size_bytes: int) -> None:
        self._size_bytes = size_bytes

    def download_audio(self, url: str, *, output_dir: Path, preferred_codec: str) -> Path:
        assert url == "https://example.com/ok"
        path = output_dir / f"audio.{preferred_codec}"
        path.write_bytes(b"x" * self._size_bytes)
        return path


class FailingDownloadClient:
    def download_audio(self, url: str, *, output_dir: Path, preferred_codec: str) -> Path:
        raise RuntimeError("primary failed")


class FakeIMusicClient:
    def source_id(self, track: IMusicTrack) -> str:
        return "imusic:test"

    def is_imusic_source(self, source_id: str) -> bool:
        return source_id.startswith("imusic:")

    def search(self, query: str, *, limit: int) -> list[IMusicTrack]:
        assert query == "artist track"
        assert limit == 5
        return [
            IMusicTrack(
                title="iMusic Short",
                artist="iMusic Artist",
                download_url="https://two.imusic.fm/public/play_mp3.php?id=1",
                duration=120,
            )
        ]

    def search_first(self, query: str) -> IMusicTrack:
        assert query == "Artist - Short"
        return IMusicTrack(
            title="Fallback Short",
            artist="Fallback Artist",
            download_url="https://two.imusic.fm/public/play_mp3.php?id=1",
            duration=181,
        )

    def download_track(self, track: IMusicTrack, *, output_dir: Path) -> Path:
        path = output_dir / "fallback.mp3"
        path.write_bytes(b"fallback-audio")
        return path


class EmptyIMusicClient:
    def search(self, query: str, *, limit: int) -> list[IMusicTrack]:
        return []

    def source_id(self, track: IMusicTrack) -> str:
        return "imusic:empty"


async def test_search_filters_long_results(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    settings = settings.__class__(
        **{**settings.__dict__, "youtube_search_enabled": True, "imusic_fallback_enabled": False}
    )
    service = SearchService(client=FakeSearchClient(), settings=settings)  # type: ignore[arg-type]

    results = await service.search("  artist   track ")

    assert [result.source_id for result in results] == ["ok"]


async def test_search_empty_imusic_does_not_fallback_to_youtube(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    service = SearchService(
        client=FailingSearchClient(),  # type: ignore[arg-type]
        settings=settings,
        imusic_client=EmptyIMusicClient(),  # type: ignore[arg-type]
    )

    results = await service.search("artist track")

    assert results == []


async def test_search_imusic_failure_raises_without_youtube(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)

    class FailingIMusicClient:
        def search(self, query: str, *, limit: int) -> list[IMusicTrack]:
            raise IMusicError("imusic down")

    service = SearchService(
        client=FailingSearchClient(),  # type: ignore[arg-type]
        settings=settings,
        imusic_client=FailingIMusicClient(),  # type: ignore[arg-type]
    )

    with pytest.raises(SearchProviderError):
        await service.search("artist track")


async def test_search_uses_imusic_before_youtube(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    service = SearchService(
        client=FailingSearchClient(),  # type: ignore[arg-type]
        settings=settings,
        imusic_client=FakeIMusicClient(),  # type: ignore[arg-type]
    )

    results = await service.search("artist track")

    assert len(results) == 1
    assert results[0].source_id.startswith("imusic:")
    assert results[0].title == "iMusic Short"
    assert results[0].uploader == "iMusic Artist"


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


async def test_download_uses_imusic_fallback_when_primary_fails(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    service = DownloadService(
        client=FailingDownloadClient(),  # type: ignore[arg-type]
        settings=settings,
        imusic_client=FakeIMusicClient(),  # type: ignore[arg-type]
    )

    audio = await service.download(SearchResult("ok", "Short", "https://example.com/ok", "Artist", 180))

    try:
        assert audio.source_id == "imusic:ok"
        assert audio.title == "Fallback Short"
        assert audio.performer == "Fallback Artist"
        assert audio.duration == 181
        assert audio.path.read_bytes() == b"fallback-audio"
    finally:
        service.cleanup(audio)


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
