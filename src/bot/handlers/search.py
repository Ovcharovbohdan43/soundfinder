from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.config import Settings
from src.infrastructure.rate_limit import RateLimitExceeded
from src.infrastructure.user_mode_store import UserMode
from src.models import SearchResult
from src.services.container import AppServices
from src.services.download_service import AudioDurationError, AudioTooLargeError, DownloadFallbackError
from src.services.search_service import SearchProviderError, SearchValidationError

router = Router()
logger = logging.getLogger(__name__)
BOT_CAPTION = '<a href="https://t.me/sound_finderbot">@sound_finderbot</a>'
PAGE_CALLBACK_PREFIX = "page:"
TRACK_CALLBACK_PREFIX = "track:"
NOOP_CALLBACK_PREFIX = "noop:"


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "?:??"
    minutes, remainder = divmod(seconds, 60)
    return f"{minutes}:{remainder:02d}"


def _trim_button(text: str, *, max_length: int = 58) -> str:
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}…"


def _build_results_keyboard(
    *,
    session_token: str,
    results: list[SearchResult],
    page: int,
    page_size: int,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    page_count = _page_count(results, page_size)
    current_page = _clamp_page(page, page_count)
    start = current_page * page_size
    end = min(start + page_size, len(results))

    for index, result in enumerate(results[start:end], start=start):
        label = _trim_button(f"{index + 1}. {result.display_title} [{_format_duration(result.duration)}]")
        buttons.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{TRACK_CALLBACK_PREFIX}{session_token}:{index}",
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


def _page_count(results: list[SearchResult], page_size: int) -> int:
    return max(1, (len(results) + page_size - 1) // page_size)


def _clamp_page(page: int, page_count: int) -> int:
    return min(max(page, 0), page_count - 1)


def _results_text(*, results: list[SearchResult], page: int, page_size: int) -> str:
    page_count = _page_count(results, page_size)
    current_page = _clamp_page(page, page_count)
    start = current_page * page_size + 1
    end = min((current_page + 1) * page_size, len(results))
    return f"Выбери трек ({start}-{end} из {len(results)}):"


@router.message(Command("cancel"))
async def cancel_handler(message: Message) -> None:
    await message.answer("Хорошо. Просто отправь новый запрос, когда захочешь найти другой трек.")


@router.message(F.text)
async def search_handler(message: Message, services: AppServices, settings: Settings) -> None:
    if message.text is None or message.text.startswith("/"):
        return

    user_id = message.from_user.id if message.from_user else message.chat.id
    if services.modes.get(user_id) != UserMode.MUSIC:
        return

    await services.analytics.record_event("music_search", user_id=user_id)
    status_message = await message.answer("Ищу подходящие треки...")

    try:
        results = await services.search.search(message.text)
    except SearchValidationError as exc:
        await status_message.edit_text(str(exc))
        return
    except SearchProviderError:
        logger.exception("Search provider failed")
        await status_message.edit_text("Не удалось выполнить поиск. Попробуй другой запрос позже.")
        return

    if not results:
        await status_message.edit_text(
            f"Ничего не нашел или все результаты длиннее {settings.max_duration_seconds} секунд."
        )
        return

    session_token = services.sessions.put_results(user_id=user_id, results=results)
    keyboard = _build_results_keyboard(
        session_token=session_token,
        results=results,
        page=0,
        page_size=settings.search_results_page_size,
    )
    await status_message.edit_text(
        _results_text(results=results, page=0, page_size=settings.search_results_page_size),
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith(PAGE_CALLBACK_PREFIX))
async def page_results_handler(
    callback: CallbackQuery,
    services: AppServices,
    settings: Settings,
) -> None:
    user_id = callback.from_user.id
    message = callback.message if isinstance(callback.message, Message) else None

    try:
        session_token, raw_page = (callback.data or "").removeprefix(PAGE_CALLBACK_PREFIX).split(":", 1)
        requested_page = int(raw_page)
    except ValueError:
        await callback.answer("Не удалось открыть страницу. Повтори поиск.", show_alert=True)
        return

    results = services.sessions.get_results(user_id=user_id, token=session_token)
    if results is None:
        await callback.answer("Этот список устарел. Повтори поиск.", show_alert=True)
        return
    if message is None:
        await callback.answer("Сообщение с результатами недоступно. Повтори поиск.", show_alert=True)
        return

    page = _clamp_page(requested_page, _page_count(results, settings.search_results_page_size))
    keyboard = _build_results_keyboard(
        session_token=session_token,
        results=results,
        page=page,
        page_size=settings.search_results_page_size,
    )
    await message.edit_text(
        _results_text(results=results, page=page, page_size=settings.search_results_page_size),
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith(NOOP_CALLBACK_PREFIX))
async def noop_handler(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith(TRACK_CALLBACK_PREFIX))
async def select_track_handler(
    callback: CallbackQuery,
    services: AppServices,
    settings: Settings,
) -> None:
    user_id = callback.from_user.id
    message = callback.message if isinstance(callback.message, Message) else None

    try:
        session_token, raw_index = (callback.data or "").removeprefix(TRACK_CALLBACK_PREFIX).split(":", 1)
        result_index = int(raw_index)
    except ValueError:
        await callback.answer("Этот результат устарел. Повтори поиск.", show_alert=True)
        return

    result = services.sessions.get_result_by_index(
        user_id=user_id,
        token=session_token,
        index=result_index,
    )

    if result is None:
        await callback.answer("Этот результат устарел. Повтори поиск.", show_alert=True)
        return

    if message is None:
        await callback.answer("Сообщение с результатами недоступно. Повтори поиск.", show_alert=True)
        return

    await callback.answer("Готовлю аудио...")
    await message.edit_text(f"Готовлю: {result.display_title}")

    try:
        async with services.limiter.acquire(user_id):
            cached = await services.cache.get(result.source_id)
            if cached is not None:
                await message.answer_audio(
                    cached.telegram_file_id,
                    title=cached.title,
                    performer=cached.performer,
                    duration=cached.duration,
                    caption=BOT_CAPTION,
                )
                await services.analytics.record_event("audio_sent", user_id=user_id)
                return

            if settings.direct_telegram_audio_url_enabled:
                try:
                    sent_message = await message.answer_audio(
                        result.url,
                        title=result.title,
                        performer=result.uploader,
                        duration=result.duration,
                        caption=BOT_CAPTION,
                    )
                    if sent_message.audio is not None:
                        await services.cache.upsert(
                            source_id=result.source_id,
                            telegram_file_id=sent_message.audio.file_id,
                            title=result.title,
                            performer=result.uploader,
                            duration=result.duration,
                        )
                    await services.analytics.record_event("audio_sent", user_id=user_id)
                    return
                except TelegramAPIError:
                    logger.warning(
                        "Direct Telegram audio URL failed, falling back to server download",
                        exc_info=True,
                    )

            audio = await services.download.download(result)
            try:
                sent_message = await message.answer_audio(
                    FSInputFile(audio.path),
                    title=audio.title,
                    performer=audio.performer,
                    duration=audio.duration,
                    caption=BOT_CAPTION,
                )
                if sent_message.audio is not None:
                    await services.cache.upsert(
                        source_id=audio.source_id,
                        telegram_file_id=sent_message.audio.file_id,
                        title=audio.title,
                        performer=audio.performer,
                        duration=audio.duration,
                    )
                await services.analytics.record_event("audio_sent", user_id=user_id)
            finally:
                services.download.cleanup(audio)
    except RateLimitExceeded:
        await callback.answer("У тебя уже есть активная загрузка. Подожди завершения.", show_alert=True)
    except AudioTooLargeError:
        await _send_error(
            callback,
            f"Файл получился больше {settings.telegram_max_audio_mb} MB. Попробуй короткий трек.",
        )
    except AudioDurationError:
        await _send_error(callback, "Трек слишком длинный для настроек бота.")
    except DownloadFallbackError:
        logger.exception("iMusic download failed")
        await _send_error(
            callback,
            "Не удалось скачать этот трек. Попробуй другой результат или другой запрос.",
        )
    except Exception:
        logger.exception("Unexpected download failure")
        await _send_error(callback, "Произошла ошибка при обработке трека.")


async def _send_error(callback: CallbackQuery, text: str) -> None:
    message = callback.message if isinstance(callback.message, Message) else None
    if message:
        await message.answer(text)
    else:
        await callback.answer(text, show_alert=True)
