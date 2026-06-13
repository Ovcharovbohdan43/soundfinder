from __future__ import annotations

from pathlib import Path

import pytest

from src.config import ConfigError, get_ytdlp_cookies_source, load_settings


def test_get_ytdlp_cookies_source_prefers_direct_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YT_DLP_COOKIES_B64", "direct")
    monkeypatch.delenv("YT_DLP_COOKIES_B64_1", raising=False)

    value, source = get_ytdlp_cookies_source()

    assert value == "direct"
    assert source == "YT_DLP_COOKIES_B64"


def test_get_ytdlp_cookies_source_joins_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YT_DLP_COOKIES_B64", raising=False)
    monkeypatch.setenv("YT_DLP_COOKIES_B64_2", "bbb")
    monkeypatch.setenv("YT_DLP_COOKIES_B64_1", "aaa")

    value, source = get_ytdlp_cookies_source()

    assert value == "aaabbb"
    assert source == "YT_DLP_COOKIES_B64 chunks (2)"


def test_get_ytdlp_cookies_source_rejects_missing_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YT_DLP_COOKIES_B64", raising=False)
    monkeypatch.setenv("YT_DLP_COOKIES_B64_1", "aaa")
    monkeypatch.setenv("YT_DLP_COOKIES_B64_3", "ccc")

    with pytest.raises(ConfigError, match="sequential"):
        get_ytdlp_cookies_source()


def test_get_ytdlp_cookies_source_rejects_mixed_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YT_DLP_COOKIES_B64", "direct")
    monkeypatch.setenv("YT_DLP_COOKIES_B64_1", "chunk")

    with pytest.raises(ConfigError, match="not both"):
        get_ytdlp_cookies_source()


def test_load_settings_uses_fast_polling_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BOT_TOKEN", "123:test")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TMP_DIR", str(tmp_path / "tmp"))
    monkeypatch.setenv("CACHE_DB_PATH", str(tmp_path / "data" / "cache.sqlite3"))
    monkeypatch.setenv("IMUSIC_FALLBACK_ENABLED", "true")
    monkeypatch.delenv("YOUTUBE_SEARCH_ENABLED", raising=False)
    monkeypatch.delenv("TELEGRAM_SINGLE_INSTANCE_LOCK", raising=False)
    monkeypatch.delenv("TELEGRAM_POLLING_TIMEOUT", raising=False)
    monkeypatch.delenv("TELEGRAM_TASKS_CONCURRENCY_LIMIT", raising=False)
    monkeypatch.delenv("DIRECT_TELEGRAM_AUDIO_URL_ENABLED", raising=False)
    monkeypatch.delenv("YOUTUBE_VIDEO_DOWNLOAD_ENABLED", raising=False)
    monkeypatch.delenv("VIDEO_STATUS_UPDATE_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("MOVIE_DOWNLOAD_ENABLED", raising=False)
    monkeypatch.delenv("KINOGO_TIMEOUT", raising=False)
    monkeypatch.delenv("IMUSIC_TIMEOUT", raising=False)
    monkeypatch.delenv("YT_DLP_COOKIES_B64", raising=False)
    for index in range(1, 6):
        monkeypatch.delenv(f"YT_DLP_COOKIES_B64_{index}", raising=False)

    settings = load_settings()

    assert settings.youtube_search_enabled is False
    assert settings.youtube_video_download_enabled is True
    assert settings.search_results_limit == 30
    assert settings.search_results_page_size == 5
    assert settings.telegram_single_instance_lock is True
    assert settings.telegram_polling_timeout == 10
    assert settings.telegram_tasks_concurrency_limit == 20
    assert settings.direct_telegram_audio_url_enabled is True
    assert settings.telegram_max_video_mb == 49
    assert settings.video_status_update_interval_seconds == 5
    assert settings.movie_download_enabled is True
    assert settings.telegram_max_movie_mb == 49
    assert settings.kinogo_timeout == 15
    assert settings.imusic_timeout == 8
