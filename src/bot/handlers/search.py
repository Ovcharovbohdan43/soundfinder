from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.config import Settings
from src.infrastructure.rate_limit import RateLimitExceeded
from src.infrastructure.yt_dlp_client import YtDlpBotBlockedError, YtDlpError
from src.models import SearchResult
from src.services.container import AppServices
from src.services.download_service import AudioDurationError, AudioTooLargeError, DownloadFallbackError
from src.services.search_service import SearchValidationError

router = Router()
logger = logging.getLogger(__name__)
BOT_CAPTION = '<a href="https://t.me/sound_finderbot">@sound_finderbot</a>'


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
    user_id: int,
    results: list[SearchResult],
    services: AppServices,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for result in results:
        token = services.sessions.put(user_id=user_id, result=result)
        label = _trim_button(f"{result.display_title} [{_format_duration(result.duration)}]")
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"track:{token}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("cancel"))
async def cancel_handler(message: Message) -> None:
    await message.answer("Хорошо. Просто отправь новый запрос, когда захочешь найти другой трек.")


@router.message(F.text)
async def search_handler(message: Message, services: AppServices, settings: Settings) -> None:
    if message.text is None or message.text.startswith("/"):
        return

    user_id = message.from_user.id if message.from_user else message.chat.id
    status_message = await message.answer("Ищу подходящие треки...")

    try:
        results = await services.search.search(message.text)
    except SearchValidationError as exc:
        await status_message.edit_text(str(exc))
        return
    except YtDlpError:
        logger.exception("Search provider failed")
        await status_message.edit_text("Не удалось выполнить поиск. Попробуй другой запрос позже.")
        return

    if not results:
        await status_message.edit_text(
            f"Ничего не нашел или все результаты длиннее {settings.max_duration_seconds} секунд."
        )
        return

    keyboard = _build_results_keyboard(user_id=user_id, results=results, services=services)
    await status_message.edit_text("Выбери трек:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("track:"))
async def select_track_handler(
    callback: CallbackQuery,
    services: AppServices,
    settings: Settings,
) -> None:
    user_id = callback.from_user.id
    token = (callback.data or "").split(":", 1)[1]
    result = services.sessions.get(user_id=user_id, token=token)
    message = callback.message if isinstance(callback.message, Message) else None

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
                return

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
    except YtDlpBotBlockedError:
        logger.exception("YouTube blocked download from server IP")
        await _send_error(callback, "Не удалось скачать этот трек. Попробуй другой результат.")
    except YtDlpError:
        logger.exception("Download provider failed")
        await _send_error(callback, "Не удалось скачать этот трек. Попробуй другой результат.")
    except Exception:
        logger.exception("Unexpected download failure")
        await _send_error(callback, "Произошла ошибка при обработке трека.")


async def _send_error(callback: CallbackQuery, text: str) -> None:
    message = callback.message if isinstance(callback.message, Message) else None
    if message:
        await message.answer(text)
    else:
        await callback.answer(text, show_alert=True)
