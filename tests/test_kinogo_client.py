from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.infrastructure.kinogo_client import KinogoClient, KinogoKind


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


def test_parse_cinemar_sources_from_fixture(client: KinogoClient) -> None:
    html = (FIXTURES_DIR / "cinemar_player.html").read_text(encoding="utf-8")

    sources = client._parse_cinemar_sources(html)  # noqa: SLF001

    assert len(sources) >= 1
    assert all(source.stream_url.startswith("https://host.cinemap.cc/") for source in sources)
    assert all(source.stream_url.endswith(".m3u8") for source in sources)


def test_parse_cinemar_sources_returns_empty_for_malformed_html(client: KinogoClient) -> None:
    assert client._parse_cinemar_sources("<html></html>") == []  # noqa: SLF001
