from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

from src.models import SearchResult


@dataclass(frozen=True)
class StoredSearchResult:
    user_id: int
    result: SearchResult
    expires_at: float


@dataclass(frozen=True)
class StoredSearchSession:
    user_id: int
    results: list[SearchResult]
    expires_at: float


class SearchSessionStore:
    def __init__(self, *, ttl_seconds: int = 900) -> None:
        self._ttl_seconds = ttl_seconds
        self._items: dict[str, StoredSearchResult] = {}
        self._sessions: dict[str, StoredSearchSession] = {}

    def put(self, *, user_id: int, result: SearchResult) -> str:
        self._cleanup()
        token = secrets.token_urlsafe(8)
        self._items[token] = StoredSearchResult(
            user_id=user_id,
            result=result,
            expires_at=time.time() + self._ttl_seconds,
        )
        return token

    def get(self, *, user_id: int, token: str) -> SearchResult | None:
        self._cleanup()
        stored = self._items.get(token)
        if stored is None or stored.user_id != user_id:
            return None
        return stored.result

    def put_results(self, *, user_id: int, results: list[SearchResult]) -> str:
        self._cleanup()
        token = secrets.token_urlsafe(8)
        self._sessions[token] = StoredSearchSession(
            user_id=user_id,
            results=results,
            expires_at=time.time() + self._ttl_seconds,
        )
        return token

    def get_results(self, *, user_id: int, token: str) -> list[SearchResult] | None:
        self._cleanup()
        stored = self._sessions.get(token)
        if stored is None or stored.user_id != user_id:
            return None
        return stored.results

    def get_result_by_index(
        self,
        *,
        user_id: int,
        token: str,
        index: int,
    ) -> SearchResult | None:
        results = self.get_results(user_id=user_id, token=token)
        if results is None or index < 0 or index >= len(results):
            return None
        return results[index]

    def _cleanup(self) -> None:
        now = time.time()
        expired_tokens = [token for token, item in self._items.items() if item.expires_at <= now]
        for token in expired_tokens:
            self._items.pop(token, None)
        expired_sessions = [
            token for token, session in self._sessions.items() if session.expires_at <= now
        ]
        for token in expired_sessions:
            self._sessions.pop(token, None)
