from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

from src.infrastructure.kinogo_client import KinogoSearchResult, KinogoSource


@dataclass(frozen=True)
class StoredMovieSearchSession:
    user_id: int
    results: list[KinogoSearchResult]
    expires_at: float


@dataclass(frozen=True)
class StoredMovieSourceSession:
    user_id: int
    page_title: str
    sources: list[KinogoSource]
    expires_at: float


class MovieSessionStore:
    def __init__(self, *, ttl_seconds: int = 900) -> None:
        self._ttl_seconds = ttl_seconds
        self._search_sessions: dict[str, StoredMovieSearchSession] = {}
        self._source_sessions: dict[str, StoredMovieSourceSession] = {}

    def put_search_results(self, *, user_id: int, results: list[KinogoSearchResult]) -> str:
        self._cleanup()
        token = secrets.token_urlsafe(8)
        self._search_sessions[token] = StoredMovieSearchSession(
            user_id=user_id,
            results=results,
            expires_at=time.time() + self._ttl_seconds,
        )
        return token

    def get_search_results(self, *, user_id: int, token: str) -> list[KinogoSearchResult] | None:
        self._cleanup()
        stored = self._search_sessions.get(token)
        if stored is None or stored.user_id != user_id:
            return None
        return stored.results

    def get_search_result_by_index(
        self,
        *,
        user_id: int,
        token: str,
        index: int,
    ) -> KinogoSearchResult | None:
        results = self.get_search_results(user_id=user_id, token=token)
        if results is None or index < 0 or index >= len(results):
            return None
        return results[index]

    def put_sources(
        self,
        *,
        user_id: int,
        page_title: str,
        sources: list[KinogoSource],
    ) -> str:
        self._cleanup()
        token = secrets.token_urlsafe(8)
        self._source_sessions[token] = StoredMovieSourceSession(
            user_id=user_id,
            page_title=page_title,
            sources=sources,
            expires_at=time.time() + self._ttl_seconds,
        )
        return token

    def get_sources(self, *, user_id: int, token: str) -> StoredMovieSourceSession | None:
        self._cleanup()
        stored = self._source_sessions.get(token)
        if stored is None or stored.user_id != user_id:
            return None
        return stored

    def get_source_by_index(
        self,
        *,
        user_id: int,
        token: str,
        index: int,
    ) -> tuple[str, KinogoSource] | None:
        stored = self.get_sources(user_id=user_id, token=token)
        if stored is None or index < 0 or index >= len(stored.sources):
            return None
        return stored.page_title, stored.sources[index]

    def _cleanup(self) -> None:
        now = time.time()
        expired_search = [
            token for token, session in self._search_sessions.items() if session.expires_at <= now
        ]
        for token in expired_search:
            self._search_sessions.pop(token, None)

        expired_sources = [
            token for token, session in self._source_sessions.items() if session.expires_at <= now
        ]
        for token in expired_sources:
            self._source_sessions.pop(token, None)
