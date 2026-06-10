from __future__ import annotations

import asyncio
import logging

from src.config import Settings
from src.infrastructure.imusic_client import IMusicClient, IMusicError
from src.infrastructure.yt_dlp_client import YtDlpClient
from src.models import SearchResult

logger = logging.getLogger(__name__)


class SearchValidationError(ValueError):
    pass


class SearchProviderError(RuntimeError):
    pass


class SearchService:
    def __init__(
        self,
        *,
        client: YtDlpClient | None,
        settings: Settings,
        imusic_client: IMusicClient | None = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._imusic_client = imusic_client

    async def search(self, query: str) -> list[SearchResult]:
        clean_query = self._validate_query(query)
        if self._imusic_client is not None:
            try:
                return await self._search_imusic(clean_query)
            except IMusicError as exc:
                logger.warning("iMusic search failed", exc_info=True)
                if not self._settings.youtube_search_enabled:
                    raise SearchProviderError("iMusic search failed") from exc

        if self._client is None:
            raise SearchProviderError("No search provider configured")

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

    async def _search_imusic(self, query: str) -> list[SearchResult]:
        assert self._imusic_client is not None
        tracks = await asyncio.to_thread(
            self._imusic_client.search,
            query,
            limit=self._settings.search_results_limit,
        )
        results: list[SearchResult] = []
        for track in tracks:
            result = SearchResult(
                source_id=self._imusic_client.source_id(track),
                title=track.title,
                url=track.download_url,
                uploader=track.artist,
                duration=track.duration,
            )
            if result.duration is None or result.duration <= self._settings.max_duration_seconds:
                results.append(result)
        return results

    def _validate_query(self, query: str) -> str:
        clean_query = " ".join(query.strip().split())
        if not clean_query:
            raise SearchValidationError("Введите название трека или исполнителя.")
        if len(clean_query) > self._settings.max_query_length:
            raise SearchValidationError(
                f"Запрос слишком длинный. Максимум: {self._settings.max_query_length} символов."
            )
        return clean_query
