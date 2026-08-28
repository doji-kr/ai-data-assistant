"""저장 계층 — Firestore 가 있으면 Firestore, 없으면 로컬 JSON 파일.

컬렉션 구조 (Firestore 기준):
  data           — 분석 데이터 {date, value, memo}
  conversations  — 대화 기록 {title, messages[], created_at}

FIREBASE_SERVICE_ACCOUNT_JSON 환경변수(서비스 계정 JSON 문자열 또는 파일 경로)가
있으면 Firestore 를 쓰고, 없으면 STORE_PATH(JSON 파일)로 동작한다.
로컬 모드는 개발/NAS 데모용이며 인터페이스는 동일하다.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import threading
import uuid


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class LocalStore:
    """파일 하나에 두 컬렉션을 담는 최소 구현. 프로세스 내 락으로 직렬화한다."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            self._write({"data": {}, "conversations": {}})

    def _read(self) -> dict:
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, obj: dict) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    # --- data ---
    def list_data(self) -> list[dict]:
        rows = [{"id": k, **v} for k, v in self._read()["data"].items()]
        return sorted(rows, key=lambda r: r["date"])

    def add_data(self, doc: dict) -> dict:
        with self._lock:
            db = self._read()
            _id = uuid.uuid4().hex[:12]
            db["data"][_id] = doc
            self._write(db)
        return {"id": _id, **doc}

    def update_data(self, _id: str, doc: dict) -> dict | None:
        with self._lock:
            db = self._read()
            if _id not in db["data"]:
                return None
            db["data"][_id] = doc
            self._write(db)
        return {"id": _id, **doc}

    def delete_data(self, _id: str) -> bool:
        with self._lock:
            db = self._read()
            if db["data"].pop(_id, None) is None:
                return False
            self._write(db)
        return True

    def count_data(self) -> int:
        return len(self._read()["data"])

    # --- conversations ---
    def list_conversations(self) -> list[dict]:
        rows = [{"id": k, **v} for k, v in self._read()["conversations"].items()]
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        # 목록 응답에는 messages 를 포함하지 않는다 (모델 A안: 상세 조회로 가져온다)
        return [{k: v for k, v in r.items() if k != "messages"} | {"message_count": len(r.get("messages", []))} for r in rows]

    def get_conversation(self, _id: str) -> dict | None:
        row = self._read()["conversations"].get(_id)
        return {"id": _id, **row} if row else None

    def save_conversation(self, doc: dict, _id: str | None = None) -> dict:
        with self._lock:
            db = self._read()
            _id = _id or uuid.uuid4().hex[:12]
            existing = db["conversations"].get(_id, {})
            doc.setdefault("created_at", existing.get("created_at") or _now_iso())
            db["conversations"][_id] = doc
            self._write(db)
        return {"id": _id, **doc}

    def delete_conversation(self, _id: str) -> bool:
        with self._lock:
            db = self._read()
            if db["conversations"].pop(_id, None) is None:
                return False
            self._write(db)
        return True


class FirestoreStore:
    """firebase-admin 기반. LocalStore 와 동일 인터페이스."""

    def __init__(self, cred_json: str):
        import firebase_admin
        from firebase_admin import credentials, firestore

        if os.path.isfile(cred_json):
            cred = credentials.Certificate(cred_json)
        else:
            cred = credentials.Certificate(json.loads(cred_json))
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    def list_data(self) -> list[dict]:
        rows = [{"id": d.id, **d.to_dict()} for d in self.db.collection("data").stream()]
        return sorted(rows, key=lambda r: r["date"])

    def add_data(self, doc: dict) -> dict:
        ref = self.db.collection("data").document()
        ref.set(doc)
        return {"id": ref.id, **doc}

    def update_data(self, _id: str, doc: dict) -> dict | None:
        ref = self.db.collection("data").document(_id)
        if not ref.get().exists:
            return None
        ref.set(doc)
        return {"id": _id, **doc}

    def delete_data(self, _id: str) -> bool:
        ref = self.db.collection("data").document(_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True

    def count_data(self) -> int:
        return len(list(self.db.collection("data").select([]).stream()))

    def list_conversations(self) -> list[dict]:
        rows = [{"id": d.id, **d.to_dict()} for d in self.db.collection("conversations").stream()]
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return [{k: v for k, v in r.items() if k != "messages"} | {"message_count": len(r.get("messages", []))} for r in rows]

    def get_conversation(self, _id: str) -> dict | None:
        d = self.db.collection("conversations").document(_id).get()
        return {"id": d.id, **d.to_dict()} if d.exists else None

    def save_conversation(self, doc: dict, _id: str | None = None) -> dict:
        col = self.db.collection("conversations")
        ref = col.document(_id) if _id else col.document()
        existing = ref.get()
        prev = existing.to_dict() if existing.exists else {}
        doc.setdefault("created_at", prev.get("created_at") or _now_iso())
        ref.set(doc)
        return {"id": ref.id, **doc}

    def delete_conversation(self, _id: str) -> bool:
        ref = self.db.collection("conversations").document(_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True


def make_store():
    cred = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if cred:
        return FirestoreStore(cred)
    return LocalStore(os.environ.get("STORE_PATH", "data/db.json"))


def seed_if_empty(store, seed_path: str) -> int:
    """저장소가 비어 있으면 seed.json 을 적재한다. 적재한 건수를 돌려준다."""
    if store.count_data() > 0 or not os.path.exists(seed_path):
        return 0
    with open(seed_path, encoding="utf-8") as f:
        rows = json.load(f)
    for r in rows:
        store.add_data({"date": r["date"], "value": r["value"], "memo": r.get("memo")})
    return len(rows)
