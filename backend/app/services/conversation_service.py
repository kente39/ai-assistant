"""대화 기록 저장/조회."""
from __future__ import annotations

from datetime import datetime, timezone

from ..database import CONVERSATION_COLLECTION, get_repo
from ..schemas import ConversationCreate


def _repo():
    return get_repo(CONVERSATION_COLLECTION)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _list_item(doc: dict) -> dict:
    msgs = doc.get("messages", [])
    first_user = next((m["content"] for m in msgs if m["role"] == "user"), "")
    return {
        "id": doc["id"],
        "title": doc.get("title", "새 대화"),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
        "message_count": len(msgs),
        "preview": first_user[:60],
    }


def list_conversations() -> list[dict]:
    return [_list_item(d) for d in _repo().list(order_by="updated_at", descending=True)]


def get_conversation(conv_id: str) -> dict | None:
    doc = _repo().get(conv_id)
    if not doc:
        return None
    return {
        "id": doc["id"],
        "title": doc.get("title", "새 대화"),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
        "messages": doc.get("messages", []),
    }


def create_conversation(payload: ConversationCreate) -> dict:
    now = _now()
    msgs = [{**m.model_dump(), "created_at": m.created_at or now} for m in payload.messages]
    doc = _repo().create({"title": payload.title, "messages": msgs, "created_at": now, "updated_at": now})
    return get_conversation(doc["id"])


def append_messages(conv_id: str | None, new_messages: list[dict]) -> str:
    """chat에서 자동 저장할 때 사용. conv_id가 없거나 존재하지 않으면 새로 만든다."""
    now = _now()
    stamped = [{**m, "created_at": now} for m in new_messages]
    if conv_id:
        doc = _repo().get(conv_id)
        if doc:
            _repo().update(conv_id, {"messages": doc.get("messages", []) + stamped, "updated_at": now})
            return conv_id
    first = next((m["content"] for m in new_messages if m["role"] == "user"), "새 대화")
    title = first[:30] + ("…" if len(first) > 30 else "")
    return _repo().create({"title": title, "messages": stamped, "created_at": now, "updated_at": now})["id"]


def delete_conversation(conv_id: str) -> bool:
    return _repo().delete(conv_id)
