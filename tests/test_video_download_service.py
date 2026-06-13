from __future__ import annotations

from src.infrastructure.yt_dlp_client import YtDlpError, classify_yt_dlp_error
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


def test_yt_dlp_filesize_error_is_preserved() -> None:
    error = classify_yt_dlp_error(RuntimeError("File is larger than max-filesize"))

    assert isinstance(error, YtDlpError)
    assert "filesize limit" in str(error)
