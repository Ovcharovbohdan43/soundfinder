from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress

from aiogram import F, Router
from aiogram.types import FSInputFile, Message

from src.bot.handlers.search import BOT_CAPTION
from src.bot.ui import MUSIC_MODE_BUTTON, YOUTUBE_VIDEO_MODE_BUTTON
from src.config import Settings
from src.infrastructure.rate_limit import RateLimitExceeded
from src.infrastructure.user_mode_store import UserMode
from src.services.container import AppServices
from src.services.video_download_service import (
    VideoDownloadError,
    VideoDownloadProgress,
    VideoTooLargeError,
)

router = Router()
logger = logging.getLogger(__name__)
SPINNER_FRAMES = ("⏳", "⌛")


@router.message(F.text)
async def youtube_video_handler(message: Message, services: AppServices, settings: Settings) -> None:
    if message.text is None or message.text.startswith("/"):
        return

    user_id = message.from_user.id if message.from_user else message.chat.id
    if services.modes.get(user_id) != UserMode.YOUTUBE_VIDEO:
        return
    if message.text in {MUSIC_MODE_BUTTON, YOUTUBE_VIDEO_MODE_BUTTON}:
        return
    if not settings.youtube_video_download_enabled:
        await message.answer("Раздел YouTube-видео сейчас выключен.")
        return

    url = message.text.strip()
    if not _is_youtube_url(url):
        await message.answer("Отправь ссылку на YouTube-видео, например https://youtu.be/...")
        return

    progress = VideoDownloadProgress()
    status_message = await message.answer(
        "⏳ Готовлю YouTube-видео в максимальном доступном качестве со звуком..."
    )
    stop_status = asyncio.Event()
    status_task = asyncio.create_task(
        _update_status_loop(
            status_message,
            progress,
            settings=settings,
            stop_status=stop_status,
        )
    )

    try:
        async with services.video_limiter.acquire(user_id):
            video = await services.video_download.download(url, progress=progress)
            stop_status.set()
            await status_task
            await status_message.edit_text(
                "📤 Видео скачано. Отправляю в Telegram..."
            )
            try:
                await message.answer_video(
                    FSInputFile(video.path),
                    caption=BOT_CAPTION,
                    duration=video.duration,
                    width=video.width,
                    height=video.height,
                    supports_streaming=True,
                )
                with suppress(Exception):
                    await status_message.delete()
            finally:
                services.video_download.cleanup(video)
    except RateLimitExceeded:
        await _stop_status(status_task, stop_status)
        await status_message.edit_text("У тебя уже скачивается видео. Подожди завершения.")
    except VideoTooLargeError:
        await _stop_status(status_task, stop_status)
        await status_message.edit_text(
            f"Видео в лучшем доступном качестве со звуком больше "
            f"{settings.telegram_max_video_mb} MB. Telegram Bot API не примет такой файл."
        )
    except VideoDownloadError:
        logger.exception("YouTube video download failed")
        await _stop_status(status_task, stop_status)
        await status_message.edit_text(
            "Не удалось скачать YouTube-видео. Попробуй другую ссылку позже."
        )
    except Exception:
        logger.exception("Unexpected YouTube video failure")
        await _stop_status(status_task, stop_status)
        await status_message.edit_text("Произошла ошибка при обработке видео.")


async def _stop_status(status_task: asyncio.Task[None], stop_status: asyncio.Event) -> None:
    stop_status.set()
    with suppress(asyncio.CancelledError):
        await status_task


async def _update_status_loop(
    message: Message,
    progress: VideoDownloadProgress,
    *,
    settings: Settings,
    stop_status: asyncio.Event,
) -> None:
    started_at = time.monotonic()
    frame_index = 0
    while not stop_status.is_set():
        snapshot = progress.snapshot()
        frame = SPINNER_FRAMES[frame_index % len(SPINNER_FRAMES)]
        frame_index += 1
        elapsed = int(time.monotonic() - started_at)
        await _safe_edit_status(
            message,
            _format_progress_text(frame=frame, elapsed=elapsed, snapshot=snapshot),
        )
        try:
            await asyncio.wait_for(
                stop_status.wait(),
                timeout=settings.video_status_update_interval_seconds,
            )
        except TimeoutError:
            continue


async def _safe_edit_status(message: Message, text: str) -> None:
    with suppress(Exception):
        await message.edit_text(text)


def _format_progress_text(*, frame: str, elapsed: int, snapshot) -> str:
    percent = snapshot.percent
    eta = _format_seconds(snapshot.eta_seconds) if snapshot.eta_seconds is not None else "оцениваю"
    downloaded = _format_bytes(snapshot.downloaded_bytes)
    total = _format_bytes(snapshot.total_bytes)
    if percent is None:
        progress_line = f"Скачано: {downloaded}"
    else:
        progress_line = f"Скачано: {percent:.0f}% ({downloaded} из {total})"

    return (
        f"{frame} Скачиваю YouTube-видео в максимальном качестве со звуком...\n"
        f"{progress_line}\n"
        f"Примерно осталось: {eta}\n"
        f"Прошло: {_format_seconds(elapsed)}"
    )


def _format_seconds(value: int | None) -> str:
    if value is None:
        return "оцениваю"
    minutes, seconds = divmod(max(0, value), 60)
    if minutes:
        return f"{minutes} мин {seconds:02d} сек"
    return f"{seconds} сек"


def _format_bytes(value: int | None) -> str:
    if not value:
        return "?"
    megabytes = value / (1024 * 1024)
    return f"{megabytes:.1f} MB"


def _is_youtube_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith(("http://", "https://")) and (
        "youtube.com/" in lowered or "youtu.be/" in lowered
    )
