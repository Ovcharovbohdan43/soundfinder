from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yt_dlp

from src.models import SearchResult

logger = logging.getLogger(__name__)


class YtDlpError(RuntimeError):
    pass


class YtDlpBotBlockedError(YtDlpError):
    pass


def classify_yt_dlp_error(exc: Exception) -> YtDlpError:
    message = str(exc).lower()
    bot_markers = (
        "confirm you're not a bot",
        "confirm you’re not a bot",
        "sign in to confirm",
        "sign in required",
        "use --cookies-from-browser or --cookies",
    )
    if any(marker in message for marker in bot_markers):
        return YtDlpBotBlockedError(
            "YouTube blocked download from this server IP. Configure YouTube cookies for Railway."
        )

    return YtDlpError("YouTube provider request failed")


class YtDlpClient:
    def __init__(
        self,
        *,
        socket_timeout: int,
        cookies_path: Path | None = None,
        proxy: str | None = None,
        player_clients: tuple[str, ...] = ("android_vr", "tv_embedded", "web_safari"),
    ) -> None:
        self._socket_timeout = socket_timeout
        self._cookies_path = cookies_path
        self._proxy = proxy
        self._player_clients = player_clients

    @property
    def has_cookies(self) -> bool:
        return self._cookies_path is not None

    def _build_options(self, **extra: Any) -> dict[str, Any]:
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": self._socket_timeout,
            "retries": 3,
            "fragment_retries": 3,
            "noplaylist": True,
            "js_runtimes": {"node": {}},
            "remote_components": ["ejs:github"],
            "extractor_args": {
                "youtube": {
                    "player_client": list(self._player_clients),
                    "player_skip": ["webpage"],
                }
            },
        }

        if self._cookies_path is not None:
            options["cookiefile"] = str(self._cookies_path)

        if self._proxy:
            options["proxy"] = self._proxy

        options.update(extra)
        return options

    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        options = self._build_options(skip_download=True, extract_flat=True)

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                payload = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        except Exception as exc:
            raise classify_yt_dlp_error(exc) from exc

        entries = (payload or {}).get("entries") or []
        results: list[SearchResult] = []
        for entry in entries:
            result = self._normalize_search_entry(entry)
            if result is not None:
                results.append(result)

        return results

    def download_audio(self, url: str, *, output_dir: Path, preferred_codec: str) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)

        options = self._build_options(
            format="m4a/bestaudio/best",
            outtmpl=str(output_dir / "%(id)s.%(ext)s"),
            restrictfilenames=True,
            postprocessors=[
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": preferred_codec,
                }
            ],
        )

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])
        except Exception as exc:
            raise classify_yt_dlp_error(exc) from exc

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
