from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

MUSIC_MODE_BUTTON = "Музыка"
YOUTUBE_VIDEO_MODE_BUTTON = "Скачать YouTube видео"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MUSIC_MODE_BUTTON)],
            [KeyboardButton(text=YOUTUBE_VIDEO_MODE_BUTTON)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
