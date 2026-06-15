from __future__ import annotations

from src.infrastructure.yt_dlp_client import (
    YtDlpBotBlockedError,
    YtDlpClient,
    YtDlpError,
    build_video_extraction_profiles,
    classify_yt_dlp_error,
    is_retryable_yt_dlp_error,
)
from src.services.video_download_service import VideoDownloadProgress


def test_video_download_progress_tracks_percent_and_eta() -> None:
    progress = VideoDownloadProgress()

    progress.hook(
        {
            "status": "downloading",
            "downloaded_bytes": 5 * 1024 * 1024,
            "total_bytes": 10 * 1024 * 1024,
            "eta": 12,
        }
    )

    snapshot = progress.snapshot()

    assert snapshot.status == "downloading"
    assert snapshot.percent == 50
    assert snapshot.eta_seconds == 12


def test_yt_dlp_filesize_error_is_not_retryable() -> None:
    error = classify_yt_dlp_error(RuntimeError("File is larger than max-filesize"))

    assert isinstance(error, YtDlpError)
    assert not isinstance(error, YtDlpBotBlockedError)
    assert "filesize limit" in str(error)
    assert is_retryable_yt_dlp_error(error) is False


def test_yt_dlp_bot_block_is_classified_and_retryable() -> None:
    error = classify_yt_dlp_error(RuntimeError("Sign in to confirm you’re not a bot"))

    assert isinstance(error, YtDlpBotBlockedError)
    assert is_retryable_yt_dlp_error(error) is True


def test_build_video_extraction_profiles_has_three_fallbacks() -> None:
    profiles = build_video_extraction_profiles(("android_vr", "tv_embedded"))

    assert len(profiles) == 3
    assert profiles[0].name == "primary"
    assert profiles[0].player_skip == ("webpage",)
    assert profiles[1].name == "webpage"
    assert profiles[1].player_skip == ()
    assert profiles[2].name == "browser"
    assert profiles[2].player_clients == ("web_safari", "mweb", "tv_embedded")


def test_yt_dlp_soft_mode_adds_headers_and_sleep() -> None:
    client = YtDlpClient(
        socket_timeout=20,
        request_sleep_seconds=1.0,
        download_sleep_min_seconds=1.0,
        download_sleep_max_seconds=3.0,
        extractor_retries=5,
    )

    options = client._build_options()

    assert client.uses_soft_mode is True
    assert options["sleep_interval_requests"] == 1.0
    assert options["sleep_interval"] == 1.0
    assert options["max_sleep_interval"] == 3.0
    assert options["extractor_retries"] == 5
    assert "User-Agent" in options["http_headers"]


def test_yt_dlp_soft_mode_disabled_with_proxy() -> None:
    client = YtDlpClient(
        socket_timeout=20,
        proxy="socks5://127.0.0.1:1080",
        request_sleep_seconds=1.0,
        download_sleep_min_seconds=1.0,
        download_sleep_max_seconds=3.0,
    )

    options = client._build_options()

    assert client.uses_soft_mode is False
    assert "sleep_interval_requests" not in options
    assert "http_headers" not in options
