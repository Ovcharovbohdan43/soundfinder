from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.bot.handlers import search, start
from src.config import ConfigError, Settings, load_settings
from src.infrastructure.audio_cache import AudioCache
from src.infrastructure.imusic_client import IMusicClient
from src.infrastructure.rate_limit import DownloadLimiter
from src.infrastructure.session_store import SearchSessionStore
from src.infrastructure.youtube_cookies import prepare_youtube_cookies
from src.infrastructure.yt_dlp_client import YtDlpClient
from src.services.container import AppServices
from src.services.download_service import DownloadService
from src.services.search_service import SearchService


def setup_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


async def build_services(settings: Settings) -> tuple[AppServices, Path | None]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)

    cookies_path = prepare_youtube_cookies(
        data_dir=settings.data_dir,
        cookies_file=settings.ytdlp_cookies_file,
        cookies_b64=settings.ytdlp_cookies_b64,
        cookies_source=settings.ytdlp_cookies_source,
    )
    if cookies_path is None:
        logging.getLogger(__name__).warning(
            "YouTube cookies are not configured. Downloads from Railway/datacenter IPs "
            "usually fail until YT_DLP_COOKIES_B64 is set."
        )

    yt_dlp_client = YtDlpClient(
        socket_timeout=settings.ytdlp_socket_timeout,
        cookies_path=cookies_path,
        proxy=settings.ytdlp_proxy,
        player_clients=settings.ytdlp_player_clients,
    )
    imusic_client = (
        IMusicClient(base_url=settings.imusic_base_url, timeout=settings.imusic_timeout)
        if settings.imusic_fallback_enabled
        else None
    )
    cache = AudioCache(settings.cache_db_path)
    await cache.init()

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
        cache=cache,
        limiter=DownloadLimiter(
            global_limit=settings.max_concurrent_downloads,
            per_user_limit=settings.max_active_downloads_per_user,
        ),
        sessions=SearchSessionStore(),
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
    dispatcher = Dispatcher(services=services, settings=settings)
    dispatcher.include_router(start.router)
    dispatcher.include_router(search.router)

    logger = logging.getLogger(__name__)
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info(
        "Music bot started in polling mode (cookies=%s, proxy=%s)",
        "yes" if cookies_path else "no",
        "yes" if settings.ytdlp_proxy else "no",
    )
    await dispatcher.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
