from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot.ui import MUSIC_MODE_BUTTON, YOUTUBE_VIDEO_MODE_BUTTON, main_menu_keyboard
from src.infrastructure.user_mode_store import UserMode
from src.services.container import AppServices

router = Router()


START_TEXT = """
Привет. Я умею искать музыку и скачивать YouTube-видео.

Как пользоваться:
1. Выбери раздел в меню.
2. Для музыки напиши название трека или исполнителя.
3. Для YouTube-видео отправь ссылку на ролик.

Команды: /help, /terms.
""".strip()


HELP_TEXT = """
Пример запроса:
imagine dragons believer

Ограничения:
- слишком длинные треки не показываются;
- аудио больше лимита Telegram не отправляется;
- музыка и видео скачиваются в разных очередях;
- YouTube-видео отправляется в максимальном доступном качестве со звуком, если размер проходит лимит Telegram.
""".strip()


TERMS_TEXT = """
Бот не обходит DRM, paywall, приватные ссылки или платный доступ.
Используй его только для контента, который разрешено скачивать и распространять.
Некоторые платформы могут запрещать скачивание своими правилами использования.
""".strip()


@router.message(Command("start"))
async def start_handler(message: Message, services: AppServices) -> None:
    user_id = message.from_user.id if message.from_user else message.chat.id
    services.modes.set(user_id, UserMode.MUSIC)
    await message.answer(START_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("terms"))
async def terms_handler(message: Message) -> None:
    await message.answer(TERMS_TEXT)


@router.message(F.text == MUSIC_MODE_BUTTON)
async def music_mode_handler(message: Message, services: AppServices) -> None:
    user_id = message.from_user.id if message.from_user else message.chat.id
    services.modes.set(user_id, UserMode.MUSIC)
    await message.answer(
        "Раздел музыки включён. Напиши название трека или исполнителя.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == YOUTUBE_VIDEO_MODE_BUTTON)
async def youtube_video_mode_handler(message: Message, services: AppServices) -> None:
    user_id = message.from_user.id if message.from_user else message.chat.id
    services.modes.set(user_id, UserMode.YOUTUBE_VIDEO)
    await message.answer(
        "Раздел YouTube-видео включён. Отправь ссылку на ролик.",
        reply_markup=main_menu_keyboard(),
    )
