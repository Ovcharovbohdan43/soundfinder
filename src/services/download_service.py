from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from src.config import Settings
from src.infrastructure.yt_dlp_client import YtDlpClient
from src.models import DownloadedAudio, SearchResult


class AudioTooLargeError(RuntimeError):
    pass


class AudioDurationError(RuntimeError):
    pass


class DownloadService:
    def __init__(self, *, client: YtDlpClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def download(self, result: SearchResult) -> DownloadedAudio:
        if result.duration is not None and result.duration > self._settings.max_duration_seconds:
            raise AudioDurationError("Track duration is above configured limit")

        self._settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(prefix=f"{result.source_id}_", dir=self._settings.tmp_dir))

        try:
            audio_path = await asyncio.to_thread(
                self._client.download_audio,
                result.url,
                output_dir=work_dir,
                preferred_codec=self._settings.preferred_audio_codec,
            )
            size_bytes = audio_path.stat().st_size
            if size_bytes > self._settings.telegram_max_audio_bytes:
                raise AudioTooLargeError(
                    f"Audio file is {size_bytes} bytes, limit is "
                    f"{self._settings.telegram_max_audio_bytes} bytes"
                )

            return DownloadedAudio(
                source_id=result.source_id,
                path=audio_path,
                title=result.title,
                performer=result.uploader,
                duration=result.duration,
                size_bytes=size_bytes,
            )
        except Exception:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise

    @staticmethod
    def cleanup(audio: DownloadedAudio) -> None:
        shutil.rmtree(audio.path.parent, ignore_errors=True)
