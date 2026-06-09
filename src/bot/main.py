from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.bot.handlers import search, start
from src.config import ConfigError, Settings, load_settings
from src.infrastructure.audio_cache import AudioCache
from src.infrastructure.rate_limit import DownloadLimiter
from src.infrastructure.session_store import SearchSessionStore
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


async def build_services(settings: Settings) -> AppServices:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)

    yt_dlp_client = YtDlpClient(socket_timeout=settings.ytdlp_socket_timeout)
    cache = AudioCache(settings.cache_db_path)
    await cache.init()

    return AppServices(
        search=SearchService(client=yt_dlp_client, settings=settings),
        download=DownloadService(client=yt_dlp_client, settings=settings),
        cache=cache,
        limiter=DownloadLimiter(
            global_limit=settings.max_concurrent_downloads,
            per_user_limit=settings.max_active_downloads_per_user,
        ),
        sessions=SearchSessionStore(),
    )


async def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    setup_logging(settings)
    services = await build_services(settings)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(services=services, settings=settings)
    dispatcher.include_router(start.router)
    dispatcher.include_router(search.router)

    logging.getLogger(__name__).info("Music bot started in polling mode")
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
