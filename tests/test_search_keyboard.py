from __future__ import annotations

from src.bot.handlers.search import _build_results_keyboard, _results_text
from src.models import SearchResult


def _result(index: int) -> SearchResult:
    return SearchResult(
        source_id=f"imusic:{index}",
        title=f"Track {index}",
        url=f"https://two.imusic.fm/public/play_mp3.php?id={index}",
        uploader="Artist",
        duration=180,
    )


def test_results_keyboard_adds_next_page_button() -> None:
    keyboard = _build_results_keyboard(
        session_token="token",
        results=[_result(index) for index in range(12)],
        page=0,
        page_size=5,
    )

    assert keyboard.inline_keyboard[0][0].text.startswith("1. Artist - Track 0")
    assert keyboard.inline_keyboard[-1][-1].text == "Дальше"
    assert keyboard.inline_keyboard[-1][-1].callback_data == "page:token:1"
    assert _results_text(results=[_result(index) for index in range(12)], page=0, page_size=5) == (
        "Выбери трек (1-5 из 12):"
    )


def test_results_keyboard_adds_previous_page_button() -> None:
    keyboard = _build_results_keyboard(
        session_token="token",
        results=[_result(index) for index in range(12)],
        page=2,
        page_size=5,
    )

    assert keyboard.inline_keyboard[0][0].text.startswith("11. Artist - Track 10")
    assert keyboard.inline_keyboard[-1][0].text == "Назад"
    assert keyboard.inline_keyboard[-1][0].callback_data == "page:token:1"
    assert _results_text(results=[_result(index) for index in range(12)], page=2, page_size=5) == (
        "Выбери трек (11-12 из 12):"
    )
