from __future__ import annotations

from src.infrastructure.session_store import SearchSessionStore
from src.models import SearchResult


def _result(index: int) -> SearchResult:
    return SearchResult(
        source_id=f"imusic:{index}",
        title=f"Track {index}",
        url=f"https://two.imusic.fm/public/play_mp3.php?id={index}",
        uploader="Artist",
        duration=180,
    )


def test_search_session_returns_result_by_index() -> None:
    store = SearchSessionStore()
    results = [_result(index) for index in range(3)]
    token = store.put_results(user_id=100, results=results)

    assert store.get_result_by_index(user_id=100, token=token, index=1) == results[1]
    assert store.get_result_by_index(user_id=100, token=token, index=3) is None


def test_search_session_is_bound_to_user() -> None:
    store = SearchSessionStore()
    token = store.put_results(user_id=100, results=[_result(1)])

    assert store.get_results(user_id=200, token=token) is None
    assert store.get_result_by_index(user_id=200, token=token, index=0) is None
