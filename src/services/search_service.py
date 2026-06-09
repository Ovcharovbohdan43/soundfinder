from __future__ import annotations

import asyncio

from src.config import Settings
from src.infrastructure.yt_dlp_client import YtDlpClient
from src.models import SearchResult


class SearchValidationError(ValueError):
    pass


class SearchService:
    def __init__(self, *, client: YtDlpClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def search(self, query: str) -> list[SearchResult]:
        clean_query = self._validate_query(query)
        results = await asyncio.to_thread(
            self._client.search,
            clean_query,
            limit=self._settings.search_results_limit,
        )

        return [
            result
            for result in results
            if result.duration is None or result.duration <= self._settings.max_duration_seconds
        ]

    def _validate_query(self, query: str) -> str:
        clean_query = " ".join(query.strip().split())
        if not clean_query:
            raise SearchValidationError("Введите название трека или исполнителя.")
        if len(clean_query) > self._settings.max_query_length:
            raise SearchValidationError(
                f"Запрос слишком длинный. Максимум: {self._settings.max_query_length} символов."
            )
        return clean_query
