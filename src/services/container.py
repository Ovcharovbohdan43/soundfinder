from __future__ import annotations

from dataclasses import dataclass

from src.infrastructure.audio_cache import AudioCache
from src.infrastructure.rate_limit import DownloadLimiter
from src.infrastructure.session_store import SearchSessionStore
from src.infrastructure.user_mode_store import UserModeStore
from src.services.download_service import DownloadService
from src.services.search_service import SearchService
from src.services.video_download_service import VideoDownloadService


@dataclass(frozen=True)
class AppServices:
    search: SearchService
    download: DownloadService
    video_download: VideoDownloadService
    cache: AudioCache
    limiter: DownloadLimiter
    video_limiter: DownloadLimiter
    sessions: SearchSessionStore
    modes: UserModeStore
