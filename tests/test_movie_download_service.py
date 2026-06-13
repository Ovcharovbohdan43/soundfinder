from __future__ import annotations

from src.services.movie_download_service import MovieDownloadProgress


def test_movie_download_progress_tracks_percent() -> None:
    progress = MovieDownloadProgress()

    progress.update(
        status="downloading",
        downloaded_bytes=25 * 1024 * 1024,
        total_bytes=50 * 1024 * 1024,
        eta_seconds=30,
    )

    snapshot = progress.snapshot()

    assert snapshot.status == "downloading"
    assert snapshot.percent == 50
    assert snapshot.eta_seconds == 30
