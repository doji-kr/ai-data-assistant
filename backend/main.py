"""나만의 AI 비서 — FastAPI 엔트리포인트.

로컬 실행:  uvicorn backend.main:app --reload
Swagger:    /docs
프론트엔드: / (frontend/ 정적 서빙 — Vercel 분리 배포 시에는 그쪽 URL 사용)
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import chat, conversations, data
from .store import make_store, seed_if_empty

app = FastAPI(
    title="나만의 AI 비서 — 스팀 인디게임 리뷰 시계열",
    description="시계열 데이터(일일 스팀 리뷰 수)를 저장·요약하고, 요약을 컨텍스트로 주입해 대화하는 AI 비서 API",
    version="1.0.0",
)

origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.store = make_store()
_seeded = seed_if_empty(app.state.store, os.environ.get("SEED_PATH", "data/seed.json"))

app.include_router(data.router)
app.include_router(conversations.router)
app.include_router(chat.router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"ok": True, "store": type(app.state.store).__name__,
            "llm_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
            "seeded_on_boot": _seeded}


_frontend = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_frontend):
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")
