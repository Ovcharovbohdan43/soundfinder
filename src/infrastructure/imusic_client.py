from __future__ import annotations

import html
import hashlib
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class IMusicError(RuntimeError):
    pass


class IMusicNotFoundError(IMusicError):
    pass


@dataclass(frozen=True)
class IMusicTrack:
    title: str
    artist: str | None
    download_url: str
    duration: int | None


class IMusicClient:
    def __init__(self, *, base_url: str, timeout: int) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._timeout = timeout
        parsed_base = urlparse(self._base_url)
        self._allowed_host = parsed_base.netloc.lower()

    def search(self, query: str, *, limit: int) -> list[IMusicTrack]:
        search_url = urljoin(self._base_url, f"search/{quote(query.strip())}")
        html_text = self._read_text(search_url)
        return self._parse_tracks(html_text)[:limit]

    def search_first(self, query: str) -> IMusicTrack:
        tracks = self.search(query, limit=1)
        if not tracks:
            raise IMusicNotFoundError("No tracks found on iMusic fallback")
        return tracks[0]

    def source_id(self, track: IMusicTrack) -> str:
        digest = hashlib.sha1(track.download_url.encode("utf-8")).hexdigest()[:16]
        return f"imusic:{digest}"

    def is_imusic_source(self, source_id: str) -> bool:
        return source_id.startswith("imusic:")

    def download_track(self, track: IMusicTrack, *, output_dir: Path) -> Path:
        self._ensure_allowed_url(track.download_url)
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / "imusic-fallback.mp3"

        request = Request(
            track.download_url,
            headers={
                "User-Agent": self._user_agent(),
                "Referer": self._base_url,
                "Accept": "audio/mpeg,audio/*,*/*",
            },
        )

        try:
            with urlopen(request, timeout=self._timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                if content_type and "audio" not in content_type and "octet-stream" not in content_type:
                    logger.warning("Unexpected iMusic content type: %s", content_type)
                with target.open("wb") as file:
                    shutil.copyfileobj(response, file)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise IMusicError("Failed to download iMusic fallback audio") from exc

        if not target.exists() or target.stat().st_size == 0:
            raise IMusicError("iMusic fallback produced an empty file")

        return target

    def _read_text(self, url: str) -> str:
        self._ensure_allowed_url(url)
        request = Request(
            url,
            headers={
                "User-Agent": self._user_agent(),
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise IMusicError("Failed to read iMusic fallback search page") from exc

        return raw.decode("utf-8", errors="replace")

    def _parse_tracks(self, html_text: str) -> list[IMusicTrack]:
        tracks: list[IMusicTrack] = []
        for item in re.findall(r"<li\b[^>]*class=[\"'][^\"']*\btrack\b[^\"']*[\"'][^>]*>", html_text):
            attrs = self._parse_attrs(item)
            raw_download_url = attrs.get("data-mp3") or attrs.get("data-url_song")
            if not raw_download_url:
                continue

            download_url = urljoin(self._base_url, html.unescape(raw_download_url))
            try:
                self._ensure_allowed_url(download_url)
            except IMusicError:
                continue

            title = attrs.get("data-title") or attrs.get("data-song") or attrs.get("data-name")
            artist = attrs.get("data-artist") or attrs.get("data-singer")
            if not title:
                title = "iMusic fallback track"

            tracks.append(
                IMusicTrack(
                    title=html.unescape(title).strip(),
                    artist=html.unescape(artist).strip() if artist else None,
                    download_url=download_url,
                    duration=self._parse_duration(attrs.get("data-duration")),
                )
            )

        return tracks

    @staticmethod
    def _parse_attrs(tag: str) -> dict[str, str]:
        attrs: dict[str, str] = {}
        for match in re.finditer(r"([\w:-]+)\s*=\s*([\"'])(.*?)\2", tag):
            attrs[match.group(1)] = match.group(3)
        return attrs

    @staticmethod
    def _parse_duration(value: str | None) -> int | None:
        if not value:
            return None
        try:
            parsed = int(value)
        except ValueError:
            return None
        if parsed > 10_000:
            return parsed // 1000
        return parsed

    def _ensure_allowed_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise IMusicError("Unsupported iMusic URL scheme")
        if parsed.netloc.lower() != self._allowed_host:
            raise IMusicError("Refusing to access non-iMusic host")

    @staticmethod
    def _user_agent() -> str:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
        )
