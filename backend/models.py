"""Pydantic 요청/응답 모델 — 입력 검증은 전부 여기서 끝낸다."""
from __future__ import annotations

import datetime as dt
from pydantic import BaseModel, Field, field_validator


class DataPointIn(BaseModel):
    """(date, value, memo) 한 건. POST/PUT 공용."""

    date: str = Field(..., description="YYYY-MM-DD")
    value: float = Field(..., description="측정값 (일일 스팀 리뷰 수)")
    memo: str | None = Field(None, max_length=500)

    @field_validator("date")
    @classmethod
    def _valid_date(cls, v: str) -> str:
        try:
            dt.date.fromisoformat(v)
        except ValueError as e:
            raise ValueError("date 는 YYYY-MM-DD 형식이어야 합니다") from e
        return v


class DataPoint(DataPointIn):
    id: str


class Message(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1, max_length=8000)


class ConversationIn(BaseModel):
    title: str | None = Field(None, max_length=200)
    messages: list[Message] = Field(..., min_length=1)


class Conversation(ConversationIn):
    id: str
    created_at: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None
    history: list[Message] = Field(default_factory=list, max_length=40)


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    used_tools: list[str] = Field(default_factory=list)
