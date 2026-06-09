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


class SearchSessionStore:
    def __init__(self, *, ttl_seconds: int = 900) -> None:
        self._ttl_seconds = ttl_seconds
        self._items: dict[str, StoredSearchResult] = {}

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

    def _cleanup(self) -> None:
        now = time.time()
        expired_tokens = [token for token, item in self._items.items() if item.expires_at <= now]
        for token in expired_tokens:
            self._items.pop(token, None)
