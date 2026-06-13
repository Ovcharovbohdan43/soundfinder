from __future__ import annotations

import secrets
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class BroadcastDraft:
    token: str
    admin_id: int
    source_chat_id: int
    source_message_id: int
    created_at: int


class BroadcastSessionStore:
    def __init__(self, *, ttl_seconds: int = 1800) -> None:
        self._ttl_seconds = ttl_seconds
        self._drafts: dict[tuple[int, str], BroadcastDraft] = {}
        self._pending_admins: dict[int, int] = {}

    def mark_waiting_for_post(self, admin_id: int) -> None:
        self._pending_admins[admin_id] = int(time.time())

    def is_waiting_for_post(self, admin_id: int) -> bool:
        self._cleanup()
        return admin_id in self._pending_admins

    def clear_waiting_for_post(self, admin_id: int) -> None:
        self._pending_admins.pop(admin_id, None)

    def put_draft(self, *, admin_id: int, source_chat_id: int, source_message_id: int) -> BroadcastDraft:
        self._cleanup()
        token = secrets.token_urlsafe(8)
        draft = BroadcastDraft(
            token=token,
            admin_id=admin_id,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
            created_at=int(time.time()),
        )
        self._drafts[(admin_id, token)] = draft
        self.clear_waiting_for_post(admin_id)
        return draft

    def get_draft(self, *, admin_id: int, token: str) -> BroadcastDraft | None:
        self._cleanup()
        return self._drafts.get((admin_id, token))

    def remove_draft(self, *, admin_id: int, token: str) -> None:
        self._drafts.pop((admin_id, token), None)

    def _cleanup(self) -> None:
        now = int(time.time())
        expired_drafts = [
            key for key, draft in self._drafts.items() if now - draft.created_at > self._ttl_seconds
        ]
        for key in expired_drafts:
            self._drafts.pop(key, None)

        expired_admins = [
            admin_id for admin_id, created_at in self._pending_admins.items()
            if now - created_at > self._ttl_seconds
        ]
        for admin_id in expired_admins:
            self._pending_admins.pop(admin_id, None)
