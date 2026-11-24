"""저장소 계층.

- FirestoreRepository : 실제 서비스용 (Firebase Firestore)
- MemoryRepository    : 키 없이 로컬에서 화면/흐름만 확인할 때 쓰는 개발용 대체 저장소

서비스 계층은 Repository 인터페이스만 알기 때문에 저장소를 바꿔도 코드가 그대로 동작한다.
"""
from __future__ import annotations

import base64
import json
import logging
import threading
import uuid
from typing import Any

from .config import settings

logger = logging.getLogger(__name__)


class Repository:
    def list(self, order_by: str | None = None, descending: bool = False) -> list[dict]: ...
    def get(self, doc_id: str) -> dict | None: ...
    def create(self, data: dict, doc_id: str | None = None) -> dict: ...
    def update(self, doc_id: str, data: dict) -> dict | None: ...
    def delete(self, doc_id: str) -> bool: ...
    def bulk_create(self, items: list[dict]) -> int: ...


# ---------------------------------------------------------------- Firestore
class FirestoreRepository(Repository):
    def __init__(self, client, collection: str):
        self.col = client.collection(collection)

    def list(self, order_by=None, descending=False):
        from google.cloud.firestore import Query

        q = self.col
        if order_by:
            q = q.order_by(order_by, direction=Query.DESCENDING if descending else Query.ASCENDING)
        return [{"id": d.id, **d.to_dict()} for d in q.stream()]

    def get(self, doc_id):
        snap = self.col.document(doc_id).get()
        return {"id": snap.id, **snap.to_dict()} if snap.exists else None

    def create(self, data, doc_id=None):
        ref = self.col.document(doc_id) if doc_id else self.col.document()
        ref.set(data)
        return {"id": ref.id, **data}

    def update(self, doc_id, data):
        ref = self.col.document(doc_id)
        if not ref.get().exists:
            return None
        ref.update(data)
        return self.get(doc_id)

    def delete(self, doc_id):
        ref = self.col.document(doc_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True

    def bulk_create(self, items):
        client = self.col._client
        count = 0
        for i in range(0, len(items), 400):  # Firestore batch 최대 500건
            batch = client.batch()
            for item in items[i : i + 400]:
                batch.set(self.col.document(), item)
                count += 1
            batch.commit()
        return count


# ---------------------------------------------------------------- Memory (dev)
class MemoryRepository(Repository):
    def __init__(self):
        self._docs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def list(self, order_by=None, descending=False):
        docs = [{"id": k, **v} for k, v in self._docs.items()]
        if order_by:
            docs.sort(key=lambda d: d.get(order_by) or "", reverse=descending)
        return docs

    def get(self, doc_id):
        v = self._docs.get(doc_id)
        return {"id": doc_id, **v} if v is not None else None

    def create(self, data, doc_id=None):
        doc_id = doc_id or uuid.uuid4().hex[:20]
        with self._lock:
            self._docs[doc_id] = dict(data)
        return {"id": doc_id, **data}

    def update(self, doc_id, data):
        with self._lock:
            if doc_id not in self._docs:
                return None
            self._docs[doc_id].update(data)
        return self.get(doc_id)

    def delete(self, doc_id):
        with self._lock:
            return self._docs.pop(doc_id, None) is not None

    def bulk_create(self, items):
        for item in items:
            self.create(item)
        return len(items)


# ---------------------------------------------------------------- 초기화
def _load_credentials():
    from firebase_admin import credentials

    raw = settings.FIREBASE_SERVICE_ACCOUNT_JSON.strip()
    if raw:
        if not raw.startswith("{"):  # base64로 넣은 경우도 허용
            raw = base64.b64decode(raw).decode("utf-8")
        return credentials.Certificate(json.loads(raw))
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        return credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
    raise RuntimeError(
        "Firebase 자격 증명이 없습니다. FIREBASE_SERVICE_ACCOUNT_JSON 또는 "
        "GOOGLE_APPLICATION_CREDENTIALS 환경 변수를 설정하세요. "
        "(로컬 테스트만 할 경우 STORAGE_BACKEND=memory)"
    )


_repos: dict[str, Repository] = {}
backend_name = settings.STORAGE_BACKEND


def get_repo(collection: str) -> Repository:
    if collection in _repos:
        return _repos[collection]

    if settings.STORAGE_BACKEND == "memory":
        repo: Repository = MemoryRepository()
    else:
        import firebase_admin
        from firebase_admin import firestore

        if not firebase_admin._apps:
            firebase_admin.initialize_app(_load_credentials())
        repo = FirestoreRepository(firestore.client(), collection)

    _repos[collection] = repo
    return repo


DATA_COLLECTION = "data"
CONVERSATION_COLLECTION = "conversations"
