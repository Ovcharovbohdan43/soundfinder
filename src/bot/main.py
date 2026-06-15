from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError

from src.bot.handlers import admin, movie, search, start, youtube_video
from src.bot.middleware import ActivityMiddleware
from src.config import ConfigError, Settings, load_settings
from src.infrastructure.analytics_store import AnalyticsStore
from src.infrastructure.audio_cache import AudioCache
from src.infrastructure.broadcast_session_store import BroadcastSessionStore
from src.infrastructure.imusic_client import IMusicClient
from src.infrastructure.kinogo_client import KinogoClient
from src.infrastructure.movie_session_store import MovieSessionStore
from src.infrastructure.rate_limit import DownloadLimiter
from src.infrastructure.single_instance import SingleInstanceLock, SingleInstanceLockError
from src.infrastructure.session_store import SearchSessionStore
from src.infrastructure.user_mode_store import UserModeStore
from src.infrastructure.youtube_cookies import prepare_youtube_cookies
from src.infrastructure.yt_dlp_client import YtDlpClient
from src.services.container import AppServices
from src.services.broadcast_service import BroadcastService
from src.services.download_service import DownloadService
from src.services.movie_download_service import MovieDownloadService
from src.services.search_service import SearchService
from src.services.video_download_service import VideoDownloadService


def setup_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


async def validate_bot_token(bot: Bot) -> None:
    logger = logging.getLogger(__name__)
    try:
        me = await bot.get_me()
    except TelegramUnauthorizedError as exc:
        logger.error(
            "BOT_TOKEN is invalid or revoked. Update Railway BOT_TOKEN from BotFather "
            "and stop any other local/Railway process using an old token."
        )
        raise SystemExit(3) from exc

    logger.info("Telegram bot authorized as @%s (id=%s)", me.username, me.id)


async def build_services(settings: Settings) -> tuple[AppServices, Path | None]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)

    cookies_path = None
    yt_dlp_client = None
    youtube_client_enabled = settings.youtube_search_enabled or settings.youtube_video_download_enabled
    if youtube_client_enabled:
        cookies_path = prepare_youtube_cookies(
            data_dir=settings.data_dir,
            cookies_file=settings.ytdlp_cookies_file,
            cookies_b64=settings.ytdlp_cookies_b64,
            cookies_source=settings.ytdlp_cookies_source,
        )
        if cookies_path is None:
            logging.getLogger(__name__).warning(
                "YouTube client is enabled, but cookies are not configured."
            )
        soft_mode = cookies_path is None and settings.ytdlp_proxy is None
        yt_dlp_client = YtDlpClient(
            socket_timeout=settings.ytdlp_socket_timeout,
            cookies_path=cookies_path,
            proxy=settings.ytdlp_proxy,
            player_clients=settings.ytdlp_player_clients,
            request_sleep_seconds=(
                settings.ytdlp_request_sleep_seconds if soft_mode else 0.0
            ),
            download_sleep_min_seconds=(
                settings.ytdlp_download_sleep_min_seconds if soft_mode else 0.0
            ),
            download_sleep_max_seconds=(
                settings.ytdlp_download_sleep_max_seconds if soft_mode else 0.0
            ),
            extractor_retries=settings.ytdlp_extractor_retries,
        )
    imusic_client = (
        IMusicClient(base_url=settings.imusic_base_url, timeout=settings.imusic_timeout)
        if settings.imusic_fallback_enabled
        else None
    )
    kinogo_client = (
        KinogoClient(
            base_url=settings.kinogo_base_url,
            timeout=settings.kinogo_timeout,
            allowed_host_suffixes=settings.kinogo_allowed_host_suffixes,
            proxy=settings.kinogo_proxy,
        )
        if settings.movie_download_enabled
        else None
    )
    cache = AudioCache(settings.cache_db_path)
    await cache.init()
    analytics = AnalyticsStore(settings.cache_db_path)
    await analytics.init()

    services = AppServices(
        search=SearchService(
            client=yt_dlp_client,
            settings=settings,
            imusic_client=imusic_client,
        ),
        download=DownloadService(
            client=yt_dlp_client,
            settings=settings,
            imusic_client=imusic_client,
        ),
        video_download=VideoDownloadService(
            client=yt_dlp_client,
            settings=settings,
        ),
        movie_download=(
            MovieDownloadService(settings=settings, referer=settings.kinogo_base_url)
            if kinogo_client is not None
            else None
        ),
        broadcast=BroadcastService(
            analytics=analytics,
            messages_per_second=settings.broadcast_messages_per_second,
        ),
        cache=cache,
        limiter=DownloadLimiter(
            global_limit=settings.max_concurrent_downloads,
            per_user_limit=settings.max_active_downloads_per_user,
        ),
        video_limiter=DownloadLimiter(
            global_limit=settings.max_concurrent_video_downloads,
            per_user_limit=settings.max_active_video_downloads_per_user,
        ),
        movie_limiter=DownloadLimiter(
            global_limit=settings.max_concurrent_movie_downloads,
            per_user_limit=settings.max_active_movie_downloads_per_user,
        ),
        analytics=analytics,
        broadcast_sessions=BroadcastSessionStore(),
        sessions=SearchSessionStore(),
        movie_sessions=MovieSessionStore(),
        modes=UserModeStore(),
        kinogo=kinogo_client,
    )
    return services, cookies_path


async def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    setup_logging(settings)
    services, cookies_path = await build_services(settings)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await validate_bot_token(bot)
    dispatcher = Dispatcher(services=services, settings=settings)
    dispatcher.message.middleware(ActivityMiddleware())
    dispatcher.callback_query.middleware(ActivityMiddleware())
    dispatcher.include_router(admin.router)
    dispatcher.include_router(start.router)
    dispatcher.include_router(movie.router)
    dispatcher.include_router(youtube_video.router)
    dispatcher.include_router(search.router)

    logger = logging.getLogger(__name__)
    instance_lock = (
        SingleInstanceLock(
            settings.data_dir / "telegram_polling.lock",
            stale_seconds=settings.telegram_lock_stale_seconds,
        )
        if settings.telegram_single_instance_lock
        else None
    )

    try:
        if instance_lock is not None:
            instance_lock.acquire()
            instance_lock.start_heartbeat()

        await bot.delete_webhook(drop_pending_updates=True)
        logger.info(
            "Music bot started in polling mode (imusic=%s, youtube_search=%s, youtube_video=%s, movie=%s, lock=%s)",
            "yes" if settings.imusic_fallback_enabled else "no",
            "yes" if settings.youtube_search_enabled else "no",
            "yes" if settings.youtube_video_download_enabled else "no",
            "yes" if settings.movie_download_enabled else "no",
            "yes" if instance_lock is not None else "no",
        )
        await dispatcher.start_polling(
            bot,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
            handle_as_tasks=True,
            polling_timeout=settings.telegram_polling_timeout,
            tasks_concurrency_limit=settings.telegram_tasks_concurrency_limit,
            close_bot_session=False,
        )
    except SingleInstanceLockError as exc:
        logger.error("%s", exc)
        raise SystemExit(2) from exc
    finally:
        if instance_lock is not None:
            await instance_lock.release()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
