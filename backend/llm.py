"""GPT 호출 계층 — 컨텍스트 주입 + 선택적 함수 호출(Function Calling).

OPENAI_BASE_URL 로 OpenAI 호환 게이트웨이(Codyssey copa 등)를 지정할 수 있다.
키가 없으면 호출부에서 503 으로 안내한다 (앱 자체는 뜬다).
"""
from __future__ import annotations

import json
import os

SYSTEM_TEMPLATE = """당신은 데이터 분석 비서입니다. 아래는 사용자의 시계열 데이터 요약입니다.

[사용자 데이터 요약]
{summary}

위 데이터를 근거로 한국어로 간결하게 답하세요. 수치를 인용할 때는 요약의 값을 그대로 쓰고,
요약에 없는 수치는 지어내지 말고 필요하면 도구를 호출해 확인하세요."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_recent_data",
            "description": "최근 N일의 원본 데이터 포인트(date, value, memo)를 조회한다. 특정 날짜·구간의 실제 값이 필요할 때 사용.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 60}},
                "required": ["days"],
            },
        },
    }
]


def _client():
    from openai import OpenAI

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    base = os.environ.get("OPENAI_BASE_URL", "").strip() or None
    return OpenAI(api_key=key, base_url=base)


def chat(summary_text: str, history: list[dict], user_message: str, recent_data_fn) -> tuple[str, list[str]]:
    """(답변, 사용한 도구 이름들). 키가 없으면 RuntimeError."""
    client = _client()
    if client is None:
        raise RuntimeError("OPENAI_API_KEY 가 설정되지 않았습니다")

    model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
    max_tokens = int(os.environ.get("OPENAI_MAX_TOKENS", "700"))

    messages = [{"role": "system", "content": SYSTEM_TEMPLATE.format(summary=summary_text)}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history][-20:]
    messages.append({"role": "user", "content": user_message})

    used_tools: list[str] = []
    for _ in range(3):  # 도구 호출 루프 상한
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=TOOLS, max_tokens=max_tokens
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return (msg.content or "", used_tools)
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            used_tools.append(tc.function.name)
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if tc.function.name == "get_recent_data":
                result = recent_data_fn(int(args.get("days", 14)))
            else:
                result = {"error": f"unknown tool {tc.function.name}"}
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False)})
    return ("도구 호출이 반복되어 답변을 마치지 못했습니다. 질문을 좁혀서 다시 시도해 주세요.", used_tools)
