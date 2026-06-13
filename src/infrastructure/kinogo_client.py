from __future__ import annotations

import base64
import html
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_HOST_SUFFIXES = (
    "kinogo.family",
    "cinemar.cc",
    "cinemar.su",
    "cinemar.one",
    "cinemar.top",
    "host.cinemap.cc",
    "video.cinemap.cc",
    "cfnd.cinemap.cc",
)
_INLINE_NOISE_MARKERS = ("b395f8f08", "9b0ff55")
_SOURCE_BLOCK_PATTERN = re.compile(
    r'"title":"((?:\\.|[^"\\])*)".*?"file":"((?:\\.|[^"\\])*)".*?"duration":(\d+)',
    re.DOTALL,
)


class KinogoError(RuntimeError):
    pass


class KinogoNotFoundError(KinogoError):
    pass


class KinogoKind(StrEnum):
    FILM = "film"
    SERIAL = "serial"


@dataclass(frozen=True)
class KinogoSearchResult:
    title: str
    url: str
    kind: KinogoKind


@dataclass(frozen=True)
class KinogoSource:
    title: str
    stream_url: str
    duration_seconds: int | None


class KinogoClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout: int,
        allowed_host_suffixes: Iterable[str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._timeout = timeout
        self._referer = self._base_url
        parsed = urlparse(self._base_url)
        self._allowed_host = parsed.netloc.lower()
        self._allowed_host_suffixes = self._normalize_allowed_host_suffixes(
            allowed_host_suffixes or DEFAULT_ALLOWED_HOST_SUFFIXES
        )

    def search(self, query: str, *, limit: int) -> list[KinogoSearchResult]:
        search_url = urljoin(
            self._base_url,
            f"?do=search&subaction=search&story={quote(query.strip())}",
        )
        html_text = self._read_text(search_url)
        return self._parse_search_results(html_text)[:limit]

    def get_page_title(self, page_url: str) -> str:
        html_text = self._read_text(page_url)
        match = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, flags=re.DOTALL | re.IGNORECASE)
        if match is None:
            match = re.search(
                r"<h2[^>]*>\s*<a[^>]+title=[\"']([^\"']+)[\"']",
                html_text,
                flags=re.DOTALL | re.IGNORECASE,
            )
            if match is None:
                return "Фильм"
            return self._clean_text(match.group(1))
        return self._clean_text(re.sub(r"<[^>]+>", "", match.group(1)))

    def get_player_url(self, page_url: str) -> str:
        html_text = self._read_text(page_url)
        match = re.search(
            r'<li[^>]*data-src=["\']([^"\']+)["\'][^>]*data-provider=["\']1["\']'
            r'|<li[^>]*data-provider=["\']1["\'][^>]*data-src=["\']([^"\']+)["\']',
            html_text,
            flags=re.IGNORECASE,
        )
        if match is None:
            raise KinogoNotFoundError("Player 1 is not available on this page")
        player_url = html.unescape(match.group(1) or match.group(2)).strip()
        self._ensure_allowed_url(player_url)
        return player_url

    def get_sources(self, player_url: str) -> list[KinogoSource]:
        html_text = self._read_text(player_url, referer=self._referer)
        sources = self._parse_cinemar_sources(html_text)
        if not sources:
            raise KinogoNotFoundError("No downloadable qualities were found in player 1")
        return sources

    def _parse_search_results(self, html_text: str) -> list[KinogoSearchResult]:
        results: list[KinogoSearchResult] = []
        for article in re.findall(
            r"<article\b[^>]*class=[\"'][^\"']*\bshortStory\b[^\"']*[\"'][^>]*>.*?</article>",
            html_text,
            flags=re.DOTALL | re.IGNORECASE,
        ):
            link_match = re.search(
                r"<h2[^>]*>\s*<a[^>]+href=[\"']([^\"']+)[\"'][^>]*title=[\"']([^\"']+)[\"']",
                article,
                flags=re.DOTALL | re.IGNORECASE,
            )
            if link_match is None:
                continue

            href = html.unescape(link_match.group(1)).strip()
            title = self._clean_text(link_match.group(2))
            url = self._normalize_page_url(href)
            kind = KinogoKind.SERIAL if "/serial" in url.lower() else KinogoKind.FILM
            results.append(KinogoSearchResult(title=title, url=url, kind=kind))
        return results

    def _parse_cinemar_sources(self, html_text: str) -> list[KinogoSource]:
        match = re.search(r'"file":"((?:\\.|[^"\\])*)"', html_text)
        if match is None:
            return []

        payload = match.group(1).encode().decode("unicode_escape")
        start = payload.find("W3s")
        if start < 0:
            return []

        decoded_text = self._decode_cinemar_payload(payload[start:])
        sources: list[KinogoSource] = []
        seen_urls: set[str] = set()

        for title_raw, file_raw, duration_raw in _SOURCE_BLOCK_PATTERN.findall(decoded_text):
            stream_url = self._normalize_stream_url(file_raw)
            if stream_url is None or stream_url in seen_urls:
                continue
            title = self._decode_json_unicode(title_raw)
            title = re.sub(r"<[^>]+>", "", title).strip() or "Качество"
            sources.append(
                KinogoSource(
                    title=title,
                    stream_url=stream_url,
                    duration_seconds=int(duration_raw),
                )
            )
            seen_urls.add(stream_url)
        return sources

    def _decode_cinemar_payload(self, payload: str) -> str:
        cleaned = re.sub(r"&[A-Za-z0-9]*?0fb(?:9f|[A-Za-z0-9]{1,3})", "", payload)
        base64_text = re.sub(r"[^A-Za-z0-9+/=]", "", cleaned)
        for marker in _INLINE_NOISE_MARKERS:
            base64_text = base64_text.replace(marker, "")

        padding = (-len(base64_text)) % 4
        return base64.b64decode(base64_text + "=" * padding).decode("latin-1")

    def _normalize_stream_url(self, raw_value: str) -> str | None:
        path = self._decode_json_unicode(raw_value).replace("\\/", "/").strip()
        if not path or ".m3u8" not in path:
            return None

        if path.startswith("//"):
            url = f"https:{path}"
        elif path.startswith("cinemap.cc/"):
            url = f"https://host.{path}"
        elif path.startswith("host.cinemap.cc/"):
            url = f"https://{path}"
        elif path.startswith("http://") or path.startswith("https://"):
            url = path
        else:
            return None

        self._ensure_allowed_url(url)
        return url

    def _read_text(self, url: str, *, referer: str | None = None) -> str:
        self._ensure_allowed_url(url)
        headers = {
            "User-Agent": self._user_agent(),
            "Accept": "text/html,application/xhtml+xml",
        }
        if referer is not None:
            headers["Referer"] = referer

        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise KinogoError("Failed to read Kinogo page") from exc

        return raw.decode("utf-8", errors="replace")

    def _normalize_page_url(self, href: str) -> str:
        if href.startswith("http://") or href.startswith("https://"):
            url = href
        else:
            url = urljoin(self._base_url, href.lstrip("/"))
        self._ensure_allowed_url(url)
        return url

    def _ensure_allowed_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise KinogoError("Only HTTP(S) URLs are allowed")
        host = parsed.netloc.lower()
        if not host:
            raise KinogoError("URL host is missing")
        if host != self._allowed_host and not any(
            host == allowed or host.endswith(f".{allowed}") for allowed in self._allowed_host_suffixes
        ):
            logger.warning("Blocked Kinogo URL host: %s", host)
            raise KinogoError("URL host is not allowed for Kinogo downloads")

    @staticmethod
    def _normalize_allowed_host_suffixes(values: Iterable[str]) -> tuple[str, ...]:
        suffixes: list[str] = []
        for value in values:
            suffix = value.strip().lower().removeprefix("http://").removeprefix("https://")
            suffix = suffix.split("/", 1)[0].strip(".")
            if suffix:
                suffixes.append(suffix)
        return tuple(dict.fromkeys(suffixes))

    @staticmethod
    def _decode_json_unicode(value: str) -> str:
        if "\\u" not in value and "\\/" not in value:
            return value
        normalized = value.replace("\\/", "/")
        try:
            return normalized.encode("utf-8").decode("unicode_escape")
        except UnicodeDecodeError:
            return normalized

    @staticmethod
    def _clean_text(value: str) -> str:
        text = html.unescape(re.sub(r"\s+", " ", value))
        return text.strip()

    @staticmethod
    def _user_agent() -> str:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
