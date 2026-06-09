from __future__ import annotations

import pytest

from src.config import ConfigError, _get_ytdlp_cookies_b64


def test_get_ytdlp_cookies_b64_prefers_direct_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YT_DLP_COOKIES_B64", "direct")
    monkeypatch.setenv("YT_DLP_COOKIES_B64_1", "chunk")

    assert _get_ytdlp_cookies_b64() == "direct"


def test_get_ytdlp_cookies_b64_joins_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YT_DLP_COOKIES_B64", raising=False)
    monkeypatch.setenv("YT_DLP_COOKIES_B64_2", "bbb")
    monkeypatch.setenv("YT_DLP_COOKIES_B64_1", "aaa")

    assert _get_ytdlp_cookies_b64() == "aaabbb"


def test_get_ytdlp_cookies_b64_rejects_missing_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YT_DLP_COOKIES_B64", raising=False)
    monkeypatch.setenv("YT_DLP_COOKIES_B64_1", "aaa")
    monkeypatch.setenv("YT_DLP_COOKIES_B64_3", "ccc")

    with pytest.raises(ConfigError, match="sequential"):
        _get_ytdlp_cookies_b64()
