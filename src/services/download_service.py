from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

from src.config import Settings
from src.infrastructure.imusic_client import IMusicClient, IMusicError, IMusicNotFoundError, IMusicTrack
from src.infrastructure.yt_dlp_client import YtDlpClient
from src.models import DownloadedAudio, SearchResult

logger = logging.getLogger(__name__)


class AudioTooLargeError(RuntimeError):
    pass


class AudioDurationError(RuntimeError):
    pass


class DownloadFallbackError(RuntimeError):
    pass


class DownloadService:
    def __init__(
        self,
        *,
        client: YtDlpClient | None,
        settings: Settings,
        imusic_client: IMusicClient | None = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._imusic_client = imusic_client

    async def download(self, result: SearchResult) -> DownloadedAudio:
        if result.duration is not None and result.duration > self._settings.max_duration_seconds:
            raise AudioDurationError("Track duration is above configured limit")

        self._settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(prefix=f"{result.source_id}_", dir=self._settings.tmp_dir))

        try:
            if self._imusic_client is not None:
                return await self._download_from_imusic(result, work_dir)

            if self._client is None:
                raise DownloadFallbackError("No download provider configured")

            try:
                audio_path = await asyncio.to_thread(
                    self._client.download_audio,
                    result.url,
                    output_dir=work_dir,
                    preferred_codec=self._settings.preferred_audio_codec,
                )
                return self._build_downloaded_audio(
                    result=result,
                    audio_path=audio_path,
                    source_id=result.source_id,
                    title=result.title,
                    performer=result.uploader,
                    duration=result.duration,
                )
            except Exception as youtube_error:
                if self._imusic_client is None:
                    raise

                logger.warning("YouTube download failed, trying iMusic fallback: %s", youtube_error)
                return await self._download_from_imusic(result, work_dir, youtube_error)
        except Exception:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise

    async def _download_from_imusic(
        self,
        result: SearchResult,
        work_dir: Path,
        primary_error: Exception | None = None,
    ) -> DownloadedAudio:
        assert self._imusic_client is not None

        try:
            if self._imusic_client.is_imusic_source(result.source_id):
                track = IMusicTrack(
                    title=result.title,
                    artist=result.uploader,
                    download_url=result.url,
                    duration=result.duration,
                )
            else:
                track = await asyncio.to_thread(self._imusic_client.search_first, result.display_title)

            if track.duration is not None and track.duration > self._settings.max_duration_seconds:
                raise AudioDurationError("Fallback track duration is above configured limit")

            audio_path = await asyncio.to_thread(
                self._imusic_client.download_track,
                track,
                output_dir=work_dir,
            )
        except (IMusicNotFoundError, IMusicError) as exc:
            raise DownloadFallbackError("iMusic download failed") from primary_error or exc

        return self._build_downloaded_audio(
            result=result,
            audio_path=audio_path,
            source_id=(
                result.source_id
                if self._imusic_client.is_imusic_source(result.source_id)
                else f"imusic:{result.source_id}"
            ),
            title=track.title or result.title,
            performer=track.artist or result.uploader,
            duration=track.duration or result.duration,
        )

    def _build_downloaded_audio(
        self,
        *,
        result: SearchResult,
        audio_path: Path,
        source_id: str,
        title: str,
        performer: str | None,
        duration: int | None,
    ) -> DownloadedAudio:
        size_bytes = audio_path.stat().st_size
        if size_bytes > self._settings.telegram_max_audio_bytes:
            raise AudioTooLargeError(
                f"Audio file is {size_bytes} bytes, limit is "
                f"{self._settings.telegram_max_audio_bytes} bytes"
            )

        return DownloadedAudio(
            source_id=source_id,
            path=audio_path,
            title=title,
            performer=performer,
            duration=duration,
            size_bytes=size_bytes,
        )

    @staticmethod
    def cleanup(audio: DownloadedAudio) -> None:
        shutil.rmtree(audio.path.parent, ignore_errors=True)
