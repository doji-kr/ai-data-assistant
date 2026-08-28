"""대화 기록 저장/조회/삭제. 목록에는 messages 를 넣지 않는다 (상세 조회 A안)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..models import ConversationIn

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
def list_conversations(req: Request):
    return req.app.state.store.list_conversations()


@router.post("", status_code=201)
def save_conversation(body: ConversationIn, req: Request):
    doc = body.model_dump()
    doc["title"] = doc.get("title") or doc["messages"][0]["content"][:40]
    return req.app.state.store.save_conversation(doc)


@router.get("/{conv_id}")
def get_conversation(conv_id: str, req: Request):
    row = req.app.state.store.get_conversation(conv_id)
    if row is None:
        raise HTTPException(404, "해당 대화가 없습니다")
    return row


@router.delete("/{conv_id}", status_code=204)
def delete_conversation(conv_id: str, req: Request):
    if not req.app.state.store.delete_conversation(conv_id):
        raise HTTPException(404, "해당 대화가 없습니다")
