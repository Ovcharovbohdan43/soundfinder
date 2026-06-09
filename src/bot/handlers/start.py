from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


START_TEXT = """
Привет. Я ищу музыку по текстовому запросу и присылаю выбранный трек аудиофайлом.

Как пользоваться:
1. Напиши название трека, исполнителя или оба варианта сразу.
2. Выбери подходящий результат из кнопок.
3. Подожди скачивание и конвертацию.

Команды: /help, /terms.
""".strip()


HELP_TEXT = """
Пример запроса:
imagine dragons believer

Ограничения:
- слишком длинные треки не показываются;
- аудио больше лимита Telegram не отправляется;
- одновременно можно запускать ограниченное число скачиваний.
""".strip()


TERMS_TEXT = """
Бот не обходит DRM, paywall, приватные ссылки или платный доступ.
Используй его только для контента, который разрешено скачивать и распространять.
Некоторые платформы могут запрещать скачивание своими правилами использования.
""".strip()


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    await message.answer(START_TEXT)


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("terms"))
async def terms_handler(message: Message) -> None:
    await message.answer(TERMS_TEXT)
