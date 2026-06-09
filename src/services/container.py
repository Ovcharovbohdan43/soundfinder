from __future__ import annotations

from dataclasses import dataclass

from src.infrastructure.audio_cache import AudioCache
from src.infrastructure.rate_limit import DownloadLimiter
from src.infrastructure.session_store import SearchSessionStore
from src.services.download_service import DownloadService
from src.services.search_service import SearchService


@dataclass(frozen=True)
class AppServices:
    search: SearchService
    download: DownloadService
    cache: AudioCache
    limiter: DownloadLimiter
    sessions: SearchSessionStore
