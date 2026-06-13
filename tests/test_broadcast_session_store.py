from __future__ import annotations

from src.infrastructure.broadcast_session_store import BroadcastSessionStore


def test_broadcast_session_store_tracks_pending_and_drafts() -> None:
    store = BroadcastSessionStore()

    store.mark_waiting_for_post(10)

    assert store.is_waiting_for_post(10)

    draft = store.put_draft(admin_id=10, source_chat_id=20, source_message_id=30)

    assert not store.is_waiting_for_post(10)
    assert store.get_draft(admin_id=10, token=draft.token) == draft

    store.remove_draft(admin_id=10, token=draft.token)

    assert store.get_draft(admin_id=10, token=draft.token) is None
