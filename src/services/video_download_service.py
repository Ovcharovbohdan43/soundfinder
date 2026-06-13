from __future__ import annotations

import asyncio
import shutil
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config import Settings
from src.infrastructure.yt_dlp_client import YtDlpClient, YtDlpError
from src.models import DownloadedVideo


class VideoDownloadError(RuntimeError):
    pass


class VideoTooLargeError(VideoDownloadError):
    pass


@dataclass(frozen=True)
class VideoProgressSnapshot:
    status: str = "starting"
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    eta_seconds: int | None = None

    @property
    def percent(self) -> float | None:
        if not self.downloaded_bytes or not self.total_bytes:
            return None
        return min(100.0, (self.downloaded_bytes / self.total_bytes) * 100)


class VideoDownloadProgress:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot = VideoProgressSnapshot()

    def hook(self, payload: dict[str, Any]) -> None:
        total_bytes = payload.get("total_bytes") or payload.get("total_bytes_estimate")
        downloaded_bytes = payload.get("downloaded_bytes")
        eta = payload.get("eta")
        with self._lock:
            self._snapshot = VideoProgressSnapshot(
                status=str(payload.get("status") or "downloading"),
                downloaded_bytes=downloaded_bytes if isinstance(downloaded_bytes, int) else None,
                total_bytes=total_bytes if isinstance(total_bytes, int) else None,
                eta_seconds=eta if isinstance(eta, int) else None,
            )

    def snapshot(self) -> VideoProgressSnapshot:
        with self._lock:
            return self._snapshot


class VideoDownloadService:
    def __init__(self, *, client: YtDlpClient | None, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def download(self, url: str, *, progress: VideoDownloadProgress) -> DownloadedVideo:
        if self._client is None:
            raise VideoDownloadError("YouTube video downloader is not configured")

        self._settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(prefix="youtube_video_", dir=self._settings.tmp_dir))
        try:
            video = await asyncio.to_thread(
                self._client.download_video,
                url,
                output_dir=work_dir,
                max_filesize_bytes=self._settings.telegram_max_video_bytes,
                progress_hook=progress.hook,
            )
        except YtDlpError as exc:
            shutil.rmtree(work_dir, ignore_errors=True)
            message = str(exc).lower()
            if "filesize" in message or "upload limit" in message:
                raise VideoTooLargeError("Downloaded video is above Telegram upload limit") from exc
            raise VideoDownloadError("YouTube video download failed") from exc

        return video

    @staticmethod
    def cleanup(video: DownloadedVideo) -> None:
        shutil.rmtree(video.path.parent, ignore_errors=True)
