from __future__ import annotations

from src.infrastructure.kinogo_client import KinogoKind, KinogoSearchResult, KinogoSource
from src.infrastructure.movie_session_store import MovieSessionStore


def test_movie_session_stores_search_results_and_sources() -> None:
    store = MovieSessionStore(ttl_seconds=900)
    results = [
        KinogoSearchResult(title="Матрица", url="https://kinogo.family/filmy/1.html", kind=KinogoKind.FILM),
    ]
    search_token = store.put_search_results(user_id=10, results=results)

    assert store.get_search_result_by_index(user_id=10, token=search_token, index=0) == results[0]
    assert store.get_search_results(user_id=11, token=search_token) is None

    sources = [
        KinogoSource(
            title="720p",
            stream_url="https://host.cinemap.cc/movies/test/hls.m3u8",
            duration_seconds=3600,
        )
    ]
    source_token = store.put_sources(user_id=10, page_title="Матрица", sources=sources)
    picked = store.get_source_by_index(user_id=10, token=source_token, index=0)

    assert picked == ("Матрица", sources[0])
