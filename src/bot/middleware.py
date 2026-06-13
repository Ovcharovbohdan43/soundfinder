from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from src.services.container import AppServices

logger = logging.getLogger(__name__)


class ActivityMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        services = data.get("services")
        if isinstance(services, AppServices):
            await self._track_event(event, services)
        return await handler(event, data)

    async def _track_event(self, event: TelegramObject, services: AppServices) -> None:
        user = None
        event_type = "update"
        if isinstance(event, Message):
            user = event.from_user
            event_type = "message"
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            event_type = "callback"

        if user is None:
            return

        try:
            await services.analytics.upsert_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            await services.analytics.record_event(event_type, user_id=user.id)
        except Exception:
            logger.warning("Failed to track bot activity", exc_info=True)
