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
SITE_TAG_PATTERNS = (
    r"\bmuzkach(?:\s+net|\.net)?\b",
    r"\btwo\.imusic\.fm\b",
    r"\bimusic\.fm\b",
    r"\bimusic\b",
)


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
        for item in re.findall(
            r"<li\b[^>]*class=[\"'][^\"']*\btrack\b[^\"']*[\"'][^>]*>.*?</li>",
            html_text,
            flags=re.DOTALL | re.IGNORECASE,
        ):
            opening_tag_match = re.match(r"<li\b[^>]*>", item, flags=re.DOTALL | re.IGNORECASE)
            if opening_tag_match is None:
                continue

            attrs = self._parse_attrs(opening_tag_match.group(0))
            raw_download_url = attrs.get("data-mp3") or attrs.get("data-url_song")
            if not raw_download_url:
                continue

            download_url = urljoin(self._base_url, html.unescape(raw_download_url))
            try:
                self._ensure_allowed_url(download_url)
            except IMusicError:
                continue

            artist, title = self._extract_track_name(item, attrs)
            artist = self._sanitize_track_text(artist)
            title = self._sanitize_track_text(title)
            if not title:
                title = self._extract_visible_text(item) or "Unknown track"
                title = self._sanitize_track_text(title) or "Unknown track"

            tracks.append(
                IMusicTrack(
                    title=title,
                    artist=artist,
                    download_url=download_url,
                    duration=self._parse_duration(attrs.get("data-duration")),
                )
            )

        return tracks

    def _extract_track_name(self, item: str, attrs: dict[str, str]) -> tuple[str | None, str | None]:
        artist = self._clean_text(attrs.get("data-artist") or attrs.get("data-singer"))
        title = self._clean_text(attrs.get("data-title") or attrs.get("data-song") or attrs.get("data-name"))
        if artist or title:
            return artist, title

        title_candidates = self._extract_text_by_class(item, ("playlist-name", "track-name", "song-name"))
        artist_candidates = self._extract_text_by_class(
            item,
            ("playlist-artist", "track-artist", "artist", "singer"),
        )

        title = title_candidates[0] if title_candidates else None
        artist = artist_candidates[0] if artist_candidates else None

        if title:
            split_artist, split_title = self._split_artist_title(title)
            artist = artist or split_artist
            title = split_title

        if not title:
            h2_text = self._extract_first_tag_text(item, "h2")
            h3_text = self._extract_first_tag_text(item, "h3")
            artist = artist or h3_text
            title = h2_text

        if title:
            split_artist, split_title = self._split_artist_title(title)
            artist = artist or split_artist
            title = split_title

        return artist, title

    @classmethod
    def _extract_text_by_class(cls, item: str, class_names: tuple[str, ...]) -> list[str]:
        values: list[str] = []
        for class_name in class_names:
            pattern = (
                r"<(?P<tag>[a-z0-9]+)\b[^>]*class=[\"'][^\"']*\b"
                + re.escape(class_name)
                + r"\b[^\"']*[\"'][^>]*>(?P<body>.*?)</(?P=tag)>"
            )
            for match in re.finditer(pattern, item, flags=re.DOTALL | re.IGNORECASE):
                text = cls._clean_text(cls._strip_tags(match.group("body")))
                if text:
                    values.append(text)
        return values

    @classmethod
    def _extract_first_tag_text(cls, item: str, tag: str) -> str | None:
        match = re.search(
            rf"<{tag}\b[^>]*>(?P<body>.*?)</{tag}>",
            item,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if match is None:
            return None
        return cls._clean_text(cls._strip_tags(match.group("body")))

    @classmethod
    def _extract_visible_text(cls, item: str) -> str | None:
        return cls._clean_text(cls._strip_tags(item))

    @staticmethod
    def _split_artist_title(value: str) -> tuple[str | None, str]:
        for separator in (" - ", " – ", " — "):
            if separator in value:
                artist, title = value.split(separator, 1)
                return artist.strip() or None, title.strip() or value
        return None, value

    @staticmethod
    def _strip_tags(value: str) -> str:
        return re.sub(r"<[^>]+>", " ", value)

    @staticmethod
    def _clean_text(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = html.unescape(value)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or None

    @classmethod
    def _sanitize_track_text(cls, value: str | None) -> str | None:
        cleaned = cls._clean_text(value)
        if not cleaned:
            return None

        for pattern in SITE_TAG_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r"\s+([)\],.!?])", r"\1", cleaned)
        cleaned = re.sub(r"([(])\s+", r"\1", cleaned)
        cleaned = re.sub(r"\s*[-–—]+\s*$", "", cleaned)
        cleaned = re.sub(r"^\s*[-–—]+\s*", "", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -–—\t\r\n")
        return cleaned or None

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
