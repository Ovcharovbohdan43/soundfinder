from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter

from src.infrastructure.analytics_store import AnalyticsStore
from src.infrastructure.broadcast_session_store import BroadcastDraft

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BroadcastResult:
    total: int
    sent: int
    blocked: int
    failed: int


class BroadcastService:
    def __init__(self, *, analytics: AnalyticsStore, messages_per_second: int) -> None:
        self._analytics = analytics
        self._delay = 1 / max(1, messages_per_second)

    async def send_to_all(self, *, bot: Bot, draft: BroadcastDraft, exclude_user_ids: set[int]) -> BroadcastResult:
        user_ids = [
            user_id
            for user_id in await self._analytics.broadcast_user_ids()
            if user_id not in exclude_user_ids
        ]
        sent = 0
        blocked = 0
        failed = 0

        for user_id in user_ids:
            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=draft.source_chat_id,
                    message_id=draft.source_message_id,
                )
                sent += 1
                await self._analytics.record_event("broadcast_sent", user_id=user_id)
            except TelegramForbiddenError:
                blocked += 1
                await self._analytics.mark_blocked(user_id)
                await self._analytics.record_event("broadcast_blocked", user_id=user_id)
            except TelegramRetryAfter as exc:
                await asyncio.sleep(exc.retry_after)
                try:
                    await bot.copy_message(
                        chat_id=user_id,
                        from_chat_id=draft.source_chat_id,
                        message_id=draft.source_message_id,
                    )
                    sent += 1
                    await self._analytics.record_event("broadcast_sent", user_id=user_id)
                except TelegramAPIError:
                    failed += 1
                    logger.warning("Broadcast retry failed for user %s", user_id, exc_info=True)
                    await self._analytics.record_event("broadcast_failed", user_id=user_id)
            except TelegramAPIError:
                failed += 1
                logger.warning("Broadcast failed for user %s", user_id, exc_info=True)
                await self._analytics.record_event("broadcast_failed", user_id=user_id)

            if self._delay > 0:
                await asyncio.sleep(self._delay)

        return BroadcastResult(total=len(user_ids), sent=sent, blocked=blocked, failed=failed)
