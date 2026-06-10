from __future__ import annotations

import pytest

from src.config import ConfigError, get_ytdlp_cookies_source


def test_get_ytdlp_cookies_source_prefers_direct_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YT_DLP_COOKIES_B64", "direct")
    monkeypatch.delenv("YT_DLP_COOKIES_B64_1", raising=False)

    value, source = get_ytdlp_cookies_source()

    assert value == "direct"
    assert source == "YT_DLP_COOKIES_B64"


def test_get_ytdlp_cookies_source_joins_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YT_DLP_COOKIES_B64", raising=False)
    monkeypatch.setenv("YT_DLP_COOKIES_B64_2", "bbb")
    monkeypatch.setenv("YT_DLP_COOKIES_B64_1", "aaa")

    value, source = get_ytdlp_cookies_source()

    assert value == "aaabbb"
    assert source == "YT_DLP_COOKIES_B64 chunks (2)"


def test_get_ytdlp_cookies_source_rejects_missing_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YT_DLP_COOKIES_B64", raising=False)
    monkeypatch.setenv("YT_DLP_COOKIES_B64_1", "aaa")
    monkeypatch.setenv("YT_DLP_COOKIES_B64_3", "ccc")

    with pytest.raises(ConfigError, match="sequential"):
        get_ytdlp_cookies_source()


def test_get_ytdlp_cookies_source_rejects_mixed_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YT_DLP_COOKIES_B64", "direct")
    monkeypatch.setenv("YT_DLP_COOKIES_B64_1", "chunk")

    with pytest.raises(ConfigError, match="not both"):
        get_ytdlp_cookies_source()
