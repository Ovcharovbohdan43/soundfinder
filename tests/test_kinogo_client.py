from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.infrastructure.kinogo_client import KinogoClient, KinogoError, KinogoKind


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def client() -> KinogoClient:
    return KinogoClient(base_url="https://kinogo.family/", timeout=5)


def test_parse_search_results_from_fixture(client: KinogoClient) -> None:
    html = (FIXTURES_DIR / "kinogo_search.html").read_text(encoding="utf-8")

    results = client._parse_search_results(html)  # noqa: SLF001

    assert len(results) >= 2
    assert any("matrica" in result.url.lower() for result in results)
    assert results[0].kind in {KinogoKind.FILM, KinogoKind.SERIAL}


def test_player_url_exists_in_movie_fixture() -> None:
    html = (FIXTURES_DIR / "kinogo_movie.html").read_text(encoding="utf-8")
    match = re.search(
        r'<li[^>]*data-src=["\']([^"\']+)["\'][^>]*data-provider=["\']1["\']'
        r'|<li[^>]*data-provider=["\']1["\'][^>]*data-src=["\']([^"\']+)["\']',
        html,
        flags=re.IGNORECASE,
    )

    assert match is not None
    player_url = match.group(1) or match.group(2)
    assert player_url.startswith("https://cinemar.cc/embed/")


def test_parse_page_details_from_movie_fixture(client: KinogoClient) -> None:
    html = (FIXTURES_DIR / "kinogo_movie.html").read_text(encoding="utf-8")

    title = client._parse_page_title(html)  # noqa: SLF001
    player_url = client._parse_player_url(html)  # noqa: SLF001

    assert title
    assert player_url.startswith("https://cinemar.cc/embed/")


def test_allowed_host_suffixes_can_be_extended() -> None:
    client = KinogoClient(
        base_url="https://kinogo.family/",
        timeout=5,
        allowed_host_suffixes=("cinemar.example",),
    )

    client._ensure_allowed_url("https://player.cinemar.example/embed/123")  # noqa: SLF001

    with pytest.raises(KinogoError, match="not allowed"):
        client._ensure_allowed_url("https://evil.example/embed/123")  # noqa: SLF001


def test_parse_cinemar_sources_from_fixture(client: KinogoClient) -> None:
    html = (FIXTURES_DIR / "cinemar_player.html").read_text(encoding="utf-8")

    sources = client._parse_cinemar_sources(html)  # noqa: SLF001

    assert len(sources) >= 1
    assert all(source.stream_url.startswith("https://host.cinemap.cc/") for source in sources)
    assert all(source.stream_url.endswith(".m3u8") for source in sources)


def test_parse_cinemar_sources_returns_empty_for_malformed_html(client: KinogoClient) -> None:
    assert client._parse_cinemar_sources("<html></html>") == []  # noqa: SLF001
