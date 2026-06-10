from __future__ import annotations

import base64
from pathlib import Path

import pytest

from src.infrastructure.youtube_cookies import filter_youtube_cookies, prepare_youtube_cookies
from src.infrastructure.yt_dlp_client import YtDlpBotBlockedError, classify_yt_dlp_error


def test_filter_youtube_cookies_keeps_only_relevant_domains() -> None:
    raw = (
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t0\tsession\tabc\n"
        ".example.com\tTRUE\t/\tTRUE\t0\tother\tdef\n"
        ".google.com\tTRUE\t/\tTRUE\t0\tauth\tghi\n"
    ).encode()

    filtered = filter_youtube_cookies(raw).decode()

    assert ".youtube.com" in filtered
    assert ".google.com" in filtered
    assert ".example.com" not in filtered


def test_prepare_youtube_cookies_from_base64(tmp_path: Path) -> None:
    raw = b"# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tsession\tabc\n"
    encoded = base64.b64encode(raw).decode()

    path = prepare_youtube_cookies(
        data_dir=tmp_path,
        cookies_file=None,
        cookies_b64=encoded,
        cookies_source="test",
    )

    assert path is not None
    assert b".youtube.com" in path.read_bytes()


def test_prepare_youtube_cookies_from_existing_file(tmp_path: Path) -> None:
    cookies_path = tmp_path / "cookies.txt"
    cookies_path.write_text("cookie-data", encoding="utf-8")

    path = prepare_youtube_cookies(
        data_dir=tmp_path,
        cookies_file=str(cookies_path),
        cookies_b64=None,
    )

    assert path == cookies_path.resolve()


def test_classify_yt_dlp_error_as_bot_blocked() -> None:
    error = classify_yt_dlp_error(
        RuntimeError("Sign in to confirm you're not a bot. Use --cookies")
    )

    assert isinstance(error, YtDlpBotBlockedError)


def test_prepare_youtube_cookies_rejects_invalid_base64(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be valid"):
        prepare_youtube_cookies(
            data_dir=tmp_path,
            cookies_file=None,
            cookies_b64="not-valid-base64",
        )
