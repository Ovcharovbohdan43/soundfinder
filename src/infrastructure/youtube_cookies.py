from __future__ import annotations

import base64
import binascii
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

YOUTUBE_COOKIE_SUFFIXES = (
    "youtube.com",
    "google.com",
    "youtu.be",
)


def filter_youtube_cookies(raw: bytes) -> bytes:
    text = raw.decode("utf-8", errors="replace")
    header_lines: list[str] = []
    cookie_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            header_lines.append(line)
            continue

        domain = line.split("\t", 1)[0].lower().lstrip(".")
        if any(domain == suffix or domain.endswith(f".{suffix}") for suffix in YOUTUBE_COOKIE_SUFFIXES):
            cookie_lines.append(line)

    if not cookie_lines:
        raise ValueError("No YouTube/Google cookies found after filtering export")

    if not header_lines:
        header_lines = ["# Netscape HTTP Cookie File"]

    filtered = "\n".join([*header_lines, *cookie_lines]) + "\n"
    return filtered.encode("utf-8")


def prepare_youtube_cookies(
    *,
    data_dir: Path,
    cookies_file: str | None,
    cookies_b64: str | None,
    cookies_source: str = "unknown",
) -> Path | None:
    if cookies_file:
        path = Path(cookies_file).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"YT_DLP_COOKIES_FILE not found: {path}")
        logger.info("Using YouTube cookies from YT_DLP_COOKIES_FILE at %s", path)
        return path

    if cookies_b64:
        target = data_dir / "youtube_cookies.txt"
        try:
            decoded = base64.b64decode(cookies_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("YouTube cookies base64 must be valid") from exc

        if not decoded.strip():
            raise ValueError("YouTube cookies base64 decoded to an empty file")

        filtered = filter_youtube_cookies(decoded)
        target.write_bytes(filtered)
        cookie_count = sum(
            1 for line in filtered.decode("utf-8").splitlines() if line.strip() and not line.startswith("#")
        )
        logger.info(
            "Wrote YouTube cookies from %s to %s (raw=%d bytes, filtered=%d bytes, entries=%d)",
            cookies_source,
            target,
            len(decoded),
            len(filtered),
            cookie_count,
        )
        return target

    default_path = data_dir / "youtube_cookies.txt"
    if default_path.is_file():
        logger.info("Using YouTube cookies from %s", default_path)
        return default_path

    return None
