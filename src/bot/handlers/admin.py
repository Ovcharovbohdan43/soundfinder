from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.config import Settings
from src.infrastructure.analytics_store import BotStats
from src.services.broadcast_service import BroadcastResult
from src.services.container import AppServices

router = Router()
logger = logging.getLogger(__name__)

BROADCAST_SEND_PREFIX = "broadcast_send:"
BROADCAST_CANCEL_PREFIX = "broadcast_cancel:"


class PendingBroadcastPostFilter(BaseFilter):
    async def __call__(self, message: Message, services: AppServices, settings: Settings) -> bool:
        if message.from_user is None:
            return False
        if not _is_admin(message, settings):
            return False
        if not services.broadcast_sessions.is_waiting_for_post(message.from_user.id):
            return False
        return message.text is None or not message.text.startswith("/")


def _is_admin(message: Message | CallbackQuery, settings: Settings) -> bool:
    user = message.from_user
    return user is not None and user.id in settings.admin_ids


async def _answer_no_access(message: Message | CallbackQuery) -> None:
    if isinstance(message, CallbackQuery):
        await message.answer("Нет доступа.", show_alert=True)
    else:
        await message.answer("Нет доступа.")


@router.message(Command("admin"))
async def admin_handler(message: Message, settings: Settings) -> None:
    if not _is_admin(message, settings):
        await _answer_no_access(message)
        return

    await message.answer(
        "Админ-панель:\n"
        "/stats - статистика\n"
        "/broadcast - создать рассылку\n"
        "/broadcast_cancel - отменить черновик рассылки"
    )


@router.message(Command("stats"))
async def stats_handler(message: Message, services: AppServices, settings: Settings) -> None:
    if not _is_admin(message, settings):
        await _answer_no_access(message)
        return

    stats = await services.analytics.stats()
    await message.answer(_format_stats(stats))


@router.message(Command("broadcast"))
async def broadcast_handler(message: Message, services: AppServices, settings: Settings) -> None:
    if not _is_admin(message, settings):
        await _answer_no_access(message)
        return
    if not settings.broadcast_enabled:
        await message.answer("Рассылки выключены через BROADCAST_ENABLED=false.")
        return

    services.broadcast_sessions.mark_waiting_for_post(message.from_user.id)
    await message.answer(
        "Отправь пост для рассылки одним сообщением.\n"
        "Можно текст, фото, видео, документ или пост с caption."
    )


@router.message(Command("broadcast_cancel"))
async def broadcast_cancel_handler(message: Message, services: AppServices, settings: Settings) -> None:
    if not _is_admin(message, settings):
        await _answer_no_access(message)
        return

    services.broadcast_sessions.clear_waiting_for_post(message.from_user.id)
    await message.answer("Черновик рассылки отменён.")


@router.message(PendingBroadcastPostFilter())
async def broadcast_draft_handler(message: Message, services: AppServices, settings: Settings) -> None:
    draft = services.broadcast_sessions.put_draft(
        admin_id=message.from_user.id,
        source_chat_id=message.chat.id,
        source_message_id=message.message_id,
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Отправить всем",
                    callback_data=f"{BROADCAST_SEND_PREFIX}{draft.token}",
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=f"{BROADCAST_CANCEL_PREFIX}{draft.token}",
                ),
            ]
        ]
    )

    await message.answer("Предпросмотр рассылки:")
    await message.bot.copy_message(
        chat_id=message.chat.id,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )
    user_count = len(await services.analytics.broadcast_user_ids())
    await message.answer(
        f"Отправить этот пост всем активным пользователям? Получателей: {user_count}.",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith(BROADCAST_CANCEL_PREFIX))
async def broadcast_cancel_callback(callback: CallbackQuery, services: AppServices, settings: Settings) -> None:
    if not _is_admin(callback, settings):
        await _answer_no_access(callback)
        return

    token = (callback.data or "").removeprefix(BROADCAST_CANCEL_PREFIX)
    services.broadcast_sessions.remove_draft(admin_id=callback.from_user.id, token=token)
    await callback.answer("Рассылка отменена.")
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Рассылка отменена.")


@router.callback_query(F.data.startswith(BROADCAST_SEND_PREFIX))
async def broadcast_send_callback(callback: CallbackQuery, services: AppServices, settings: Settings) -> None:
    if not _is_admin(callback, settings):
        await _answer_no_access(callback)
        return
    if not settings.broadcast_enabled:
        await callback.answer("Рассылки выключены.", show_alert=True)
        return

    token = (callback.data or "").removeprefix(BROADCAST_SEND_PREFIX)
    draft = services.broadcast_sessions.get_draft(admin_id=callback.from_user.id, token=token)
    if draft is None:
        await callback.answer("Черновик устарел. Создай рассылку заново.", show_alert=True)
        return

    await callback.answer("Рассылка запущена.")
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Рассылка запущена. Отправляю пост пользователям...")

    await services.analytics.record_event("broadcast_started", user_id=callback.from_user.id)
    result = await services.broadcast.send_to_all(
        bot=callback.bot,
        draft=draft,
        exclude_user_ids=set(settings.admin_ids),
    )
    services.broadcast_sessions.remove_draft(admin_id=callback.from_user.id, token=token)
    await services.analytics.record_event("broadcast_finished", user_id=callback.from_user.id)

    text = _format_broadcast_result(result)
    if isinstance(callback.message, Message):
        await callback.message.answer(text)
    else:
        await callback.bot.send_message(callback.from_user.id, text)


def _format_stats(stats: BotStats) -> str:
    today = stats.events_today
    total = stats.events_total
    request_today = sum(today.get(name, 0) for name in ("music_search", "youtube_video_request", "movie_search"))
    request_total = sum(total.get(name, 0) for name in ("music_search", "youtube_video_request", "movie_search"))
    lines = [
        "Статистика бота",
        "",
        f"Пользователей всего: {stats.total_users}",
        f"Активных сегодня: {stats.active_today}",
        f"Активных за 7 дней: {stats.active_7d}",
        "",
        f"Запросов сегодня: {request_today}",
        f"Запросов всего: {request_total}",
        f"Музыкальных поисков сегодня: {today.get('music_search', 0)}",
        f"YouTube-запросов сегодня: {today.get('youtube_video_request', 0)}",
        f"Кино-поисков сегодня: {today.get('movie_search', 0)}",
        f"Скачиваний аудио сегодня: {today.get('audio_sent', 0)}",
        f"Скачиваний видео сегодня: {today.get('video_sent', 0)}",
        f"Скачиваний фильмов сегодня: {today.get('movie_sent', 0)}",
        f"Рассылок отправлено сегодня: {today.get('broadcast_sent', 0)}",
    ]
    return "\n".join(html.escape(line) for line in lines)


def _format_broadcast_result(result: BroadcastResult) -> str:
    return (
        "Рассылка завершена.\n"
        f"Получателей: {result.total}\n"
        f"Отправлено: {result.sent}\n"
        f"Заблокировали бота: {result.blocked}\n"
        f"Ошибок: {result.failed}"
    )
