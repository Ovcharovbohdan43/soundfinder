from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yt_dlp

from src.models import DownloadedVideo, SearchResult

logger = logging.getLogger(__name__)

_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class YtDlpError(RuntimeError):
    pass


class YtDlpBotBlockedError(YtDlpError):
    pass


@dataclass(frozen=True)
class _YoutubeExtractionProfile:
    name: str
    player_clients: tuple[str, ...]
    player_skip: tuple[str, ...] = ()


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
            "YouTube blocked download from this server IP after trying multiple extraction modes."
        )

    filesize_markers = (
        "larger than max-filesize",
        "file is larger than max-filesize",
        "exceeds the maximum filesize",
        "above telegram upload limit",
        "above configured filesize limit",
    )
    if any(marker in message for marker in filesize_markers):
        return YtDlpError("Requested media is above configured filesize limit")

    return YtDlpError("YouTube provider request failed")


def is_retryable_yt_dlp_error(exc: YtDlpError) -> bool:
    if isinstance(exc, YtDlpBotBlockedError):
        return True

    message = str(exc).lower()
    retry_markers = (
        "unable to extract",
        "http error",
        "connection",
        "timed out",
        "timeout",
        "temporary failure",
        "player response",
        "precondition check failed",
        "requested format is not available",
        "provider request failed",
    )
    return any(marker in message for marker in retry_markers)


def build_video_extraction_profiles(
    primary_clients: tuple[str, ...],
) -> tuple[_YoutubeExtractionProfile, ...]:
    return (
        _YoutubeExtractionProfile(
            name="primary",
            player_clients=primary_clients,
            player_skip=("webpage",),
        ),
        _YoutubeExtractionProfile(
            name="webpage",
            player_clients=primary_clients,
        ),
        _YoutubeExtractionProfile(
            name="browser",
            player_clients=("web_safari", "mweb", "tv_embedded"),
        ),
    )


class _YtDlpLogger:
    def debug(self, msg: str) -> None:
        logger.debug("%s", msg)

    def info(self, msg: str) -> None:
        logger.debug("%s", msg)

    def warning(self, msg: str) -> None:
        logger.warning("%s", msg)

    def error(self, msg: str) -> None:
        logger.debug("%s", msg)


class YtDlpClient:
    def __init__(
        self,
        *,
        socket_timeout: int,
        cookies_path: Path | None = None,
        proxy: str | None = None,
        player_clients: tuple[str, ...] = ("android_vr", "tv_embedded", "web_safari"),
        request_sleep_seconds: float = 0.0,
        download_sleep_min_seconds: float = 0.0,
        download_sleep_max_seconds: float = 0.0,
        extractor_retries: int = 3,
    ) -> None:
        self._socket_timeout = socket_timeout
        self._cookies_path = cookies_path
        self._proxy = proxy
        self._player_clients = player_clients
        self._request_sleep_seconds = request_sleep_seconds
        self._download_sleep_min_seconds = download_sleep_min_seconds
        self._download_sleep_max_seconds = download_sleep_max_seconds
        self._extractor_retries = extractor_retries

    @property
    def has_cookies(self) -> bool:
        return self._cookies_path is not None

    @property
    def uses_soft_mode(self) -> bool:
        return self._cookies_path is None and self._proxy is None

    def _build_options(
        self,
        *,
        profile: _YoutubeExtractionProfile | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        youtube_args: dict[str, list[str]] = {
            "player_client": list(
                profile.player_clients if profile is not None else self._player_clients
            ),
        }
        if profile is not None and profile.player_skip:
            youtube_args["player_skip"] = list(profile.player_skip)
        elif profile is None:
            youtube_args["player_skip"] = ["webpage"]

        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "logger": _YtDlpLogger(),
            "socket_timeout": self._socket_timeout,
            "retries": 3,
            "fragment_retries": 3,
            "extractor_retries": self._extractor_retries,
            "noplaylist": True,
            "js_runtimes": {"node": {}},
            "remote_components": ["ejs:github"],
            "extractor_args": {"youtube": youtube_args},
        }

        if self.uses_soft_mode:
            options["http_headers"] = {
                "User-Agent": _BROWSER_USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
            }
            if self._request_sleep_seconds > 0:
                options["sleep_interval_requests"] = self._request_sleep_seconds
            if self._download_sleep_min_seconds > 0:
                options["sleep_interval"] = self._download_sleep_min_seconds
            if self._download_sleep_max_seconds > 0:
                options["max_sleep_interval"] = self._download_sleep_max_seconds

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

    def download_video(
        self,
        url: str,
        *,
        output_dir: Path,
        max_filesize_bytes: int,
        progress_hook: Callable[[dict[str, Any]], None] | None = None,
    ) -> DownloadedVideo:
        output_dir.mkdir(parents=True, exist_ok=True)
        profiles = build_video_extraction_profiles(self._player_clients)
        last_error: YtDlpError | None = None

        for index, profile in enumerate(profiles):
            try:
                return self._download_video_with_profile(
                    url,
                    output_dir=output_dir,
                    max_filesize_bytes=max_filesize_bytes,
                    progress_hook=progress_hook,
                    profile=profile,
                )
            except YtDlpError as exc:
                last_error = exc
                if not is_retryable_yt_dlp_error(exc) or index == len(profiles) - 1:
                    raise
                logger.warning(
                    "YouTube profile %s failed (%s); trying next profile",
                    profile.name,
                    exc,
                )
            except Exception as exc:
                classified = classify_yt_dlp_error(exc)
                last_error = classified
                if not is_retryable_yt_dlp_error(classified) or index == len(profiles) - 1:
                    raise classified from exc
                logger.warning(
                    "YouTube profile %s failed (%s); trying next profile",
                    profile.name,
                    classified,
                )

        if last_error is not None:
            raise last_error
        raise YtDlpError("YouTube video download failed")

    def _download_video_with_profile(
        self,
        url: str,
        *,
        output_dir: Path,
        max_filesize_bytes: int,
        progress_hook: Callable[[dict[str, Any]], None] | None,
        profile: _YoutubeExtractionProfile,
    ) -> DownloadedVideo:
        max_filesize = max_filesize_bytes - (1024 * 1024)
        format_selector = (
            f"best[ext=mp4][vcodec!=none][acodec!=none][filesize<{max_filesize}]/"
            f"best[ext=mp4][vcodec!=none][acodec!=none][filesize_approx<{max_filesize}]/"
            f"best[vcodec!=none][acodec!=none][filesize<{max_filesize}]/"
            f"best[vcodec!=none][acodec!=none][filesize_approx<{max_filesize}]/"
            "best[ext=mp4][vcodec!=none][acodec!=none]/"
            "best[vcodec!=none][acodec!=none]"
        )
        options = self._build_options(
            profile=profile,
            format=format_selector,
            outtmpl=str(output_dir / "%(id)s.%(ext)s"),
            restrictfilenames=True,
            merge_output_format="mp4",
            max_filesize=max_filesize_bytes,
            progress_hooks=[progress_hook] if progress_hook is not None else [],
        )

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as exc:
            raise classify_yt_dlp_error(exc) from exc

        requested_downloads = (info or {}).get("requested_downloads") or []
        filepath = None
        if requested_downloads:
            filepath = requested_downloads[0].get("filepath")
        if not filepath:
            filepath = (info or {}).get("filepath") or (info or {}).get("_filename")
        if not filepath:
            candidates = sorted(output_dir.glob("*.*"), key=lambda path: path.stat().st_mtime)
            if not candidates:
                raise YtDlpError("Downloaded video file was not produced")
            video_path = candidates[-1]
        else:
            video_path = Path(filepath)

        if not video_path.exists():
            raise YtDlpError("Downloaded video file was not produced")

        size_bytes = video_path.stat().st_size
        if size_bytes > max_filesize_bytes:
            raise YtDlpError("Downloaded video is above Telegram upload limit")

        return DownloadedVideo(
            path=video_path,
            title=str((info or {}).get("title") or "YouTube video"),
            duration=(info or {}).get("duration") if isinstance((info or {}).get("duration"), int) else None,
            width=(info or {}).get("width") if isinstance((info or {}).get("width"), int) else None,
            height=(info or {}).get("height") if isinstance((info or {}).get("height"), int) else None,
            size_bytes=size_bytes,
        )

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
