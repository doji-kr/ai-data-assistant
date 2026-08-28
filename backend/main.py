"""나만의 AI 비서 — FastAPI 엔트리포인트.

로컬 실행:  uvicorn backend.main:app --reload
Swagger:    /docs
프론트엔드: / (frontend/ 정적 서빙 — Vercel 분리 배포 시에는 그쪽 URL 사용)
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
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


_root = os.path.join(os.path.dirname(__file__), "..")
_report = os.path.join(_root, "REPORT.md")


@app.get("/api/report", tags=["meta"], response_class=PlainTextResponse,
         summary="분석 리포트 원문(Markdown) — 프론트가 렌더링해 같은 페이지에서 보여준다")
def report():
    if not os.path.isfile(_report):
        raise HTTPException(404, "REPORT.md 가 없습니다")
    with open(_report, encoding="utf-8") as f:
        return f.read()


@app.get("/api/report.md", tags=["meta"], summary="분석 리포트 md 파일 다운로드")
def report_download():
    if not os.path.isfile(_report):
        raise HTTPException(404, "REPORT.md 가 없습니다")
    return FileResponse(_report, media_type="text/markdown", filename="REPORT.md")


_images = os.path.join(_root, "images")
if os.path.isdir(_images):
    app.mount("/images", StaticFiles(directory=_images), name="images")

_frontend = os.path.join(_root, "frontend")
if os.path.isdir(_frontend):
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")
