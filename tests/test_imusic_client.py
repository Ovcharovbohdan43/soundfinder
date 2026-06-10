from __future__ import annotations

import pytest

from src.infrastructure.imusic_client import IMusicClient, IMusicError


def test_parse_tracks_from_imusic_html() -> None:
    client = IMusicClient(base_url="https://two.imusic.fm/", timeout=3)
    html = """
    <li class="track" data-title="Track &amp; Name" data-artist="Artist"
        data-duration="181000" data-mp3="/public/play_mp3.php?id=123"></li>
    """

    tracks = client._parse_tracks(html)  # noqa: SLF001

    assert len(tracks) == 1
    assert tracks[0].title == "Track & Name"
    assert tracks[0].artist == "Artist"
    assert tracks[0].duration == 181
    assert tracks[0].download_url == "https://two.imusic.fm/public/play_mp3.php?id=123"


def test_parse_tracks_from_nested_imusic_html() -> None:
    client = IMusicClient(base_url="https://two.imusic.fm/", timeout=3)
    html = """
    <li class="track" data-duration="128000" data-mp3="/public/play_mp3.php?id=321">
      <div class="playlist-btn-down"></div>
      <h2 class="playlist-name"><a href="/song/321">Принц - Роза</a></h2>
      <h3 class="playlist-artist">Артист</h3>
    </li>
    """

    tracks = client._parse_tracks(html)  # noqa: SLF001

    assert len(tracks) == 1
    assert tracks[0].artist == "Артист"
    assert tracks[0].title == "Роза"
    assert tracks[0].duration == 128


def test_parse_tracks_rejects_external_download_host() -> None:
    client = IMusicClient(base_url="https://two.imusic.fm/", timeout=3)
    html = """
    <li class="track" data-title="Track" data-artist="Artist"
        data-mp3="https://example.com/track.mp3"></li>
    """

    assert client._parse_tracks(html) == []  # noqa: SLF001


def test_allowed_url_rejects_non_imusic_host() -> None:
    client = IMusicClient(base_url="https://two.imusic.fm/", timeout=3)

    with pytest.raises(IMusicError):
        client._ensure_allowed_url("https://example.com/track.mp3")  # noqa: SLF001
