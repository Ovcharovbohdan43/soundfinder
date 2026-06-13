from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.bot.handlers.search import BOT_CAPTION
from src.bot.ui import MOVIE_MODE_BUTTON, MUSIC_MODE_BUTTON, YOUTUBE_VIDEO_MODE_BUTTON
from src.config import Settings
from src.infrastructure.kinogo_client import KinogoClient, KinogoError, KinogoNotFoundError
from src.infrastructure.rate_limit import RateLimitExceeded
from src.infrastructure.user_mode_store import UserMode
from src.services.container import AppServices
from src.services.movie_download_service import (
    MovieDownloadError,
    MovieDownloadProgress,
    MovieTooLargeError,
)

router = Router()
logger = logging.getLogger(__name__)
SPINNER_FRAMES = ("⏳", "⌛")
PAGE_CALLBACK_PREFIX = "movie_page:"
PICK_CALLBACK_PREFIX = "movie_pick:"
QUALITY_CALLBACK_PREFIX = "movie_quality:"
NOOP_CALLBACK_PREFIX = "movie_noop:"
MENU_BUTTONS = {MUSIC_MODE_BUTTON, YOUTUBE_VIDEO_MODE_BUTTON, MOVIE_MODE_BUTTON}


@router.message(F.text)
async def movie_search_handler(message: Message, services: AppServices, settings: Settings) -> None:
    if message.text is None or message.text.startswith("/"):
        return

    user_id = message.from_user.id if message.from_user else message.chat.id
    if services.modes.get(user_id) != UserMode.MOVIE:
        return
    if message.text in MENU_BUTTONS:
        return
    if not settings.movie_download_enabled:
        await message.answer("Раздел фильмов сейчас выключен.")
        return
    if services.kinogo is None:
        await message.answer("Kinogo-источник не настроен.")
        return

    query = message.text.strip()
    if len(query) < 2:
        await message.answer("Напиши название фильма или сериала.")
        return

    status_message = await message.answer("Ищу фильмы и сериалы...")
    try:
        results = await asyncio.to_thread(services.kinogo.search, query, limit=settings.search_results_limit)
    except KinogoError:
        logger.exception("Kinogo search failed")
        await status_message.edit_text("Не удалось выполнить поиск. Попробуй позже.")
        return

    if not results:
        await status_message.edit_text("Ничего не нашёл. Попробуй другой запрос.")
        return

    session_token = services.movie_sessions.put_search_results(user_id=user_id, results=results)
    keyboard = _build_search_keyboard(
        session_token=session_token,
        results=results,
        page=0,
        page_size=settings.search_results_page_size,
    )
    await status_message.edit_text(
        _search_results_text(results=results, page=0, page_size=settings.search_results_page_size),
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith(PAGE_CALLBACK_PREFIX))
async def movie_page_handler(callback: CallbackQuery, services: AppServices, settings: Settings) -> None:
    user_id = callback.from_user.id
    message = callback.message if isinstance(callback.message, Message) else None
    try:
        session_token, raw_page = (callback.data or "").removeprefix(PAGE_CALLBACK_PREFIX).split(":", 1)
        requested_page = int(raw_page)
    except ValueError:
        await callback.answer("Не удалось открыть страницу. Повтори поиск.", show_alert=True)
        return

    results = services.movie_sessions.get_search_results(user_id=user_id, token=session_token)
    if results is None or message is None:
        await callback.answer("Этот список устарел. Повтори поиск.", show_alert=True)
        return

    page = _clamp_page(requested_page, _page_count(results, settings.search_results_page_size))
    keyboard = _build_search_keyboard(
        session_token=session_token,
        results=results,
        page=page,
        page_size=settings.search_results_page_size,
    )
    await message.edit_text(
        _search_results_text(results=results, page=page, page_size=settings.search_results_page_size),
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith(PICK_CALLBACK_PREFIX))
async def movie_pick_handler(callback: CallbackQuery, services: AppServices, settings: Settings) -> None:
    user_id = callback.from_user.id
    message = callback.message if isinstance(callback.message, Message) else None
    try:
        session_token, raw_index = (callback.data or "").removeprefix(PICK_CALLBACK_PREFIX).split(":", 1)
        result_index = int(raw_index)
    except ValueError:
        await callback.answer("Этот результат устарел. Повтори поиск.", show_alert=True)
        return

    result = services.movie_sessions.get_search_result_by_index(
        user_id=user_id,
        token=session_token,
        index=result_index,
    )
    if result is None or message is None or services.kinogo is None:
        await callback.answer("Этот результат устарел. Повтори поиск.", show_alert=True)
        return

    await callback.answer("Загружаю качества...")
    await message.edit_text(f"Проверяю плеер 1: {result.title}")

    try:
        page_title, sources = await asyncio.gather(
            asyncio.to_thread(services.kinogo.get_page_title, result.url),
            _load_sources(services.kinogo, result.url),
        )
    except KinogoNotFoundError as exc:
        await message.edit_text(str(exc))
        return
    except KinogoError:
        logger.exception("Failed to load Kinogo sources")
        await message.edit_text("Не удалось получить ссылки для скачивания. Попробуй другой результат.")
        return

    if not sources:
        await message.edit_text("Для этого фильма не найдено доступных качеств.")
        return

    source_token = services.movie_sessions.put_sources(
        user_id=user_id,
        page_title=page_title,
        sources=sources,
    )
    keyboard = _build_quality_keyboard(session_token=source_token, sources=sources)
    await message.edit_text(f"Выбери качество для «{page_title}»:", reply_markup=keyboard)


@router.callback_query(F.data.startswith(QUALITY_CALLBACK_PREFIX))
async def movie_quality_handler(
    callback: CallbackQuery,
    services: AppServices,
    settings: Settings,
) -> None:
    user_id = callback.from_user.id
    message = callback.message if isinstance(callback.message, Message) else None
    try:
        session_token, raw_index = (callback.data or "").removeprefix(QUALITY_CALLBACK_PREFIX).split(":", 1)
        source_index = int(raw_index)
    except ValueError:
        await callback.answer("Этот выбор устарел. Повтори поиск.", show_alert=True)
        return

    picked = services.movie_sessions.get_source_by_index(
        user_id=user_id,
        token=session_token,
        index=source_index,
    )
    if picked is None or message is None or services.movie_download is None:
        await callback.answer("Этот выбор устарел. Повтори поиск.", show_alert=True)
        return

    page_title, source = picked
    await callback.answer("Начинаю скачивание...")
    progress = MovieDownloadProgress()
    status_message = await message.edit_text(
        f"⏳ Готовлю «{page_title}» ({source.title})..."
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
        async with services.movie_limiter.acquire(user_id):
            movie = await services.movie_download.download(
                source=source,
                page_title=page_title,
                progress=progress,
            )
            stop_status.set()
            await status_task
            await status_message.edit_text("📤 Файл скачан. Отправляю в Telegram...")
            try:
                caption = f"{page_title}\n{BOT_CAPTION}"
                if movie.path.suffix.lower() == ".mp4":
                    await message.answer_video(
                        FSInputFile(movie.path),
                        caption=caption,
                        duration=movie.duration,
                        supports_streaming=True,
                    )
                else:
                    await message.answer_document(FSInputFile(movie.path), caption=caption)
                with suppress(Exception):
                    await status_message.delete()
            finally:
                services.movie_download.cleanup(movie)
    except RateLimitExceeded:
        await _stop_status(status_task, stop_status)
        await status_message.edit_text("У тебя уже скачивается фильм. Подожди завершения.")
    except MovieTooLargeError:
        await _stop_status(status_task, stop_status)
        await status_message.edit_text(
            f"Файл больше {settings.telegram_max_movie_mb} MB. Telegram Bot API не примет такой размер."
        )
    except MovieDownloadError:
        logger.exception("Movie download failed")
        await _stop_status(status_task, stop_status)
        await status_message.edit_text("Не удалось скачать фильм. Попробуй другое качество.")
    except Exception:
        logger.exception("Unexpected movie download failure")
        await _stop_status(status_task, stop_status)
        await status_message.edit_text("Произошла ошибка при обработке фильма.")


@router.callback_query(F.data.startswith(NOOP_CALLBACK_PREFIX))
async def movie_noop_handler(callback: CallbackQuery) -> None:
    await callback.answer()


async def _load_sources(client: KinogoClient, page_url: str):
    player_url = await asyncio.to_thread(client.get_player_url, page_url)
    return await asyncio.to_thread(client.get_sources, player_url)


async def _stop_status(status_task: asyncio.Task[None], stop_status: asyncio.Event) -> None:
    stop_status.set()
    with suppress(asyncio.CancelledError):
        await status_task


async def _update_status_loop(
    message: Message,
    progress: MovieDownloadProgress,
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
                timeout=settings.movie_status_update_interval_seconds,
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
        f"{frame} Скачиваю фильм...\n"
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


def _build_search_keyboard(
    *,
    session_token: str,
    results,
    page: int,
    page_size: int,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    page_count = _page_count(results, page_size)
    current_page = _clamp_page(page, page_count)
    start = current_page * page_size
    end = min(start + page_size, len(results))

    for index, result in enumerate(results[start:end], start=start):
        label = _trim_button(f"{index + 1}. {result.title}")
        buttons.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{PICK_CALLBACK_PREFIX}{session_token}:{index}",
                )
            ]
        )

    if page_count > 1:
        navigation: list[InlineKeyboardButton] = []
        if current_page > 0:
            navigation.append(
                InlineKeyboardButton(
                    text="Назад",
                    callback_data=f"{PAGE_CALLBACK_PREFIX}{session_token}:{current_page - 1}",
                )
            )
        navigation.append(
            InlineKeyboardButton(
                text=f"{current_page + 1}/{page_count}",
                callback_data=f"{NOOP_CALLBACK_PREFIX}{session_token}",
            )
        )
        if current_page < page_count - 1:
            navigation.append(
                InlineKeyboardButton(
                    text="Дальше",
                    callback_data=f"{PAGE_CALLBACK_PREFIX}{session_token}:{current_page + 1}",
                )
            )
        buttons.append(navigation)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_quality_keyboard(*, session_token: str, sources) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for index, source in enumerate(sources[:20]):
        label = _trim_button(f"{index + 1}. {source.title}")
        buttons.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{QUALITY_CALLBACK_PREFIX}{session_token}:{index}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _search_results_text(*, results, page: int, page_size: int) -> str:
    page_count = _page_count(results, page_size)
    current_page = _clamp_page(page, page_count)
    start = current_page * page_size + 1
    end = min((current_page + 1) * page_size, len(results))
    return f"Выбери фильм или сериал ({start}-{end} из {len(results)}):"


def _page_count(results, page_size: int) -> int:
    return max(1, (len(results) + page_size - 1) // page_size)


def _clamp_page(page: int, page_count: int) -> int:
    return min(max(page, 0), page_count - 1)


def _trim_button(text: str, *, max_length: int = 58) -> str:
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}…"
