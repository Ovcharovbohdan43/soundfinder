from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from src.config import Settings
from src.infrastructure.kinogo_client import KinogoSource
from src.models import DownloadedMovie


class MovieDownloadError(RuntimeError):
    pass


class MovieTooLargeError(MovieDownloadError):
    pass


@dataclass(frozen=True)
class MovieProgressSnapshot:
    status: str = "starting"
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    eta_seconds: int | None = None

    @property
    def percent(self) -> float | None:
        if not self.downloaded_bytes or not self.total_bytes:
            return None
        return min(100.0, (self.downloaded_bytes / self.total_bytes) * 100)


class MovieDownloadProgress:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot = MovieProgressSnapshot()

    def update(
        self,
        *,
        status: str,
        downloaded_bytes: int | None = None,
        total_bytes: int | None = None,
        eta_seconds: int | None = None,
    ) -> None:
        with self._lock:
            self._snapshot = MovieProgressSnapshot(
                status=status,
                downloaded_bytes=downloaded_bytes,
                total_bytes=total_bytes,
                eta_seconds=eta_seconds,
            )

    def snapshot(self) -> MovieProgressSnapshot:
        with self._lock:
            return self._snapshot


class MovieDownloadService:
    _TIME_PATTERN = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
    _SIZE_PATTERN = re.compile(r"size=\s*([0-9]+)kB")
    _SPEED_PATTERN = re.compile(r"speed=\s*([0-9.]+)x")

    def __init__(self, *, settings: Settings, referer: str) -> None:
        self._settings = settings
        self._referer = referer

    async def download(
        self,
        *,
        source: KinogoSource,
        page_title: str,
        progress: MovieDownloadProgress,
    ) -> DownloadedMovie:
        self._settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(prefix="movie_", dir=self._settings.tmp_dir))
        output_path = work_dir / "movie.mp4"

        try:
            await asyncio.to_thread(
                self._run_ffmpeg,
                source.stream_url,
                output_path,
                source.duration_seconds,
                progress,
            )
        except MovieTooLargeError:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise
        except Exception as exc:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise MovieDownloadError("Movie download failed") from exc

        if not output_path.exists() or output_path.stat().st_size == 0:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise MovieDownloadError("Movie download produced an empty file")

        size_bytes = output_path.stat().st_size
        if size_bytes > self._settings.telegram_max_movie_bytes:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise MovieTooLargeError("Downloaded movie is above Telegram upload limit")

        return DownloadedMovie(
            path=output_path,
            title=page_title,
            duration=source.duration_seconds,
            size_bytes=size_bytes,
        )

    def _run_ffmpeg(
        self,
        stream_url: str,
        output_path: Path,
        duration_seconds: int | None,
        progress: MovieDownloadProgress,
    ) -> None:
        headers = f"Referer: {self._referer}\r\n"
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "info",
            "-headers",
            headers,
            "-i",
            stream_url,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            "-y",
            str(output_path),
        ]
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stderr is not None

        for line in process.stderr:
            self._update_progress_from_line(
                line,
                duration_seconds=duration_seconds,
                output_path=output_path,
                progress=progress,
            )
            if output_path.exists():
                size_bytes = output_path.stat().st_size
                if size_bytes > self._settings.telegram_max_movie_bytes:
                    process.kill()
                    raise MovieTooLargeError("Movie exceeds configured Telegram upload limit")

        return_code = process.wait()
        if return_code != 0:
            raise MovieDownloadError(f"ffmpeg exited with code {return_code}")

        progress.update(status="finished", downloaded_bytes=output_path.stat().st_size)

    def _update_progress_from_line(
        self,
        line: str,
        *,
        duration_seconds: int | None,
        output_path: Path,
        progress: MovieDownloadProgress,
    ) -> None:
        downloaded_bytes = output_path.stat().st_size if output_path.exists() else None
        total_bytes = None
        eta_seconds = None

        time_match = self._TIME_PATTERN.search(line)
        if time_match and duration_seconds:
            hours = int(time_match.group(1))
            minutes = int(time_match.group(2))
            seconds = float(time_match.group(3))
            current_seconds = int(hours * 3600 + minutes * 60 + seconds)
            if duration_seconds > 0:
                total_bytes = max(downloaded_bytes or 1, 1)
                if downloaded_bytes and current_seconds > 0:
                    estimated_total = int(downloaded_bytes / (current_seconds / duration_seconds))
                    total_bytes = estimated_total
                    remaining = max(0, duration_seconds - current_seconds)
                    eta_seconds = remaining

        size_match = self._SIZE_PATTERN.search(line)
        if size_match:
            downloaded_bytes = int(size_match.group(1)) * 1024

        progress.update(
            status="downloading",
            downloaded_bytes=downloaded_bytes,
            total_bytes=total_bytes,
            eta_seconds=eta_seconds,
        )

    @staticmethod
    def cleanup(movie: DownloadedMovie) -> None:
        shutil.rmtree(movie.path.parent, ignore_errors=True)
