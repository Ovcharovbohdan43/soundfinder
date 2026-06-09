from __future__ import annotations

from pathlib import Path
from typing import Any

import yt_dlp

from src.models import SearchResult


class YtDlpError(RuntimeError):
    pass


class YtDlpClient:
    def __init__(self, *, socket_timeout: int) -> None:
        self._socket_timeout = socket_timeout

    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "socket_timeout": self._socket_timeout,
        }

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                payload = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        except Exception as exc:  # yt-dlp raises several non-public exception classes.
            raise YtDlpError("Search provider failed") from exc

        entries = (payload or {}).get("entries") or []
        results: list[SearchResult] = []
        for entry in entries:
            result = self._normalize_search_entry(entry)
            if result is not None:
                results.append(result)

        return results

    def download_audio(self, url: str, *, output_dir: Path, preferred_codec: str) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)

        options: dict[str, Any] = {
            "format": "m4a/bestaudio/best",
            "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "restrictfilenames": True,
            "socket_timeout": self._socket_timeout,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": preferred_codec,
                }
            ],
        }

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])
        except Exception as exc:
            raise YtDlpError("Audio download failed") from exc

        candidates = sorted(output_dir.glob(f"*.{preferred_codec}"))
        if not candidates:
            raise YtDlpError("Downloaded audio file was not produced")

        return candidates[0]

    @staticmethod
    def _normalize_search_entry(entry: dict[str, Any]) -> SearchResult | None:
        source_id = str(entry.get("id") or "").strip()
        title = str(entry.get("title") or "").strip()
        url = str(entry.get("webpage_url") or entry.get("url") or "").strip()

        if not source_id or not title or not url:
            return None

        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={source_id}"

        duration = entry.get("duration")
        if not isinstance(duration, int):
            duration = None

        uploader = entry.get("uploader") or entry.get("channel")
        return SearchResult(
            source_id=source_id,
            title=title,
            url=url,
            uploader=str(uploader).strip() if uploader else None,
            duration=duration,
            thumbnail_url=entry.get("thumbnail"),
        )
