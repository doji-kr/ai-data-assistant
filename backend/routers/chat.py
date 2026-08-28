"""AI 챗 — 요약 조회 → 시스템 프롬프트 주입 → GPT 호출 → 대화 자동 저장."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .. import llm
from ..models import ChatRequest, ChatResponse
from ..summary import compute_summary, summary_to_prompt

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(body: ChatRequest, req: Request):
    store = req.app.state.store
    rows = store.list_data()
    summary_text = summary_to_prompt(compute_summary(rows))

    def recent_data(days: int) -> list[dict]:
        return rows[-days:]

    history = [m.model_dump() for m in body.history]
    try:
        reply, used_tools = llm.chat(summary_text, history, body.message, recent_data)
    except RuntimeError as e:
        raise HTTPException(503, str(e) + " — 서버 환경변수에 키를 넣고 재시작하세요")
    except Exception as e:  # 게이트웨이/네트워크 오류를 사용자에게 그대로 노출하지 않는다
        raise HTTPException(502, f"AI 호출 실패: {type(e).__name__}")

    # 자동 저장: 기존 대화가 있으면 이어붙이고, 없으면 새로 만든다
    messages = history + [
        {"role": "user", "content": body.message},
        {"role": "assistant", "content": reply},
    ]
    prev = store.get_conversation(body.conversation_id) if body.conversation_id else None
    title = (prev or {}).get("title") or body.message[:40]
    saved = store.save_conversation({"title": title, "messages": messages},
                                    _id=body.conversation_id if prev else None)
    return ChatResponse(reply=reply, conversation_id=saved["id"], used_tools=used_tools)
