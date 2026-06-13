from __future__ import annotations

from dataclasses import dataclass

from src.infrastructure.audio_cache import AudioCache
from src.infrastructure.kinogo_client import KinogoClient
from src.infrastructure.movie_session_store import MovieSessionStore
from src.infrastructure.rate_limit import DownloadLimiter
from src.infrastructure.session_store import SearchSessionStore
from src.infrastructure.user_mode_store import UserModeStore
from src.services.download_service import DownloadService
from src.services.movie_download_service import MovieDownloadService
from src.services.search_service import SearchService
from src.services.video_download_service import VideoDownloadService


@dataclass(frozen=True)
class AppServices:
    search: SearchService
    download: DownloadService
    video_download: VideoDownloadService
    movie_download: MovieDownloadService | None
    cache: AudioCache
    limiter: DownloadLimiter
    video_limiter: DownloadLimiter
    movie_limiter: DownloadLimiter
    sessions: SearchSessionStore
    movie_sessions: MovieSessionStore
    modes: UserModeStore
    kinogo: KinogoClient | None
