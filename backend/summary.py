"""시계열 요약 — /api/data/summary 가 반환하고 챗 시스템 프롬프트에 주입된다.

적용 기법 (과제 요구: 2가지 이상)
  1. 이동평균: 최근 7일 이동평균으로 노이즈를 걷어낸 수준을 본다
  2. 구간 비교(변화율): 최근 14일 평균 vs 직전 14일 평균으로 추세를 판정한다
  3. 요일별 집계: 요일 패턴(주말/평일)을 본다
"""
from __future__ import annotations

import datetime as dt
import statistics

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def compute_summary(rows: list[dict]) -> dict:
    if not rows:
        return {"period": None, "count": 0, "metrics": {}, "trend": "데이터 없음"}

    rows = sorted(rows, key=lambda r: r["date"])
    values = [float(r["value"]) for r in rows]

    # 기본 통계
    metrics = {
        "total": round(sum(values), 2),
        "average": round(statistics.mean(values), 2),
        "max": max(values),
        "min": min(values),
        "stdev": round(statistics.pstdev(values), 2),
    }
    peak = max(rows, key=lambda r: float(r["value"]))

    # 7일 이동평균 (마지막 값)
    tail7 = values[-7:]
    ma7 = round(statistics.mean(tail7), 2)

    # 구간 비교: 최근 14일 vs 직전 14일
    recent, prev = values[-14:], values[-28:-14]
    trend = "판정 불가 (구간 부족)"
    change_pct = None
    if prev:
        a, b = statistics.mean(prev), statistics.mean(recent)
        change_pct = round((b - a) / a * 100, 1) if a else None
        if change_pct is None:
            trend = "판정 불가"
        elif change_pct > 10:
            trend = f"상승 (최근 14일 평균 {change_pct:+}%)"
        elif change_pct < -10:
            trend = f"하락 (최근 14일 평균 {change_pct:+}%)"
        else:
            trend = f"유지 (최근 14일 평균 {change_pct:+}%)"

    # 요일별 평균
    by_wd: dict[int, list[float]] = {}
    for r in rows:
        try:
            wd = dt.date.fromisoformat(r["date"]).weekday()
        except ValueError:
            continue
        by_wd.setdefault(wd, []).append(float(r["value"]))
    weekday_avg = {WEEKDAYS[k]: round(statistics.mean(v), 1) for k, v in sorted(by_wd.items())}
    best_wd = max(weekday_avg, key=weekday_avg.get) if weekday_avg else None

    return {
        "period": f"{rows[0]['date']} ~ {rows[-1]['date']}",
        "count": len(rows),
        "metrics": metrics,
        "moving_average_7d": ma7,
        "trend": trend,
        "change_pct_14d": change_pct,
        "peak": {"date": peak["date"], "value": peak["value"], "memo": peak.get("memo")},
        "weekday_average": weekday_avg,
        "best_weekday": best_wd,
    }


def summary_to_prompt(s: dict) -> str:
    """요약 dict → 시스템 프롬프트 주입용 텍스트."""
    if not s.get("count"):
        return "아직 저장된 데이터가 없습니다."
    m = s["metrics"]
    return (
        f"- 데이터: 스팀 인디게임 신작 추적(indiepulse) 일일 신규 리뷰 수\n"
        f"- 기간: {s['period']} (총 {s['count']}일)\n"
        f"- 합계 {m['total']:.0f}건 · 일평균 {m['average']}건 · 최대 {m['max']:.0f}건 · 최소 {m['min']:.0f}건 · 표준편차 {m['stdev']}\n"
        f"- 최고점: {s['peak']['date']} {s['peak']['value']}건 ({s['peak'].get('memo') or ''})\n"
        f"- 최근 7일 이동평균: {s['moving_average_7d']}건\n"
        f"- 추세: {s['trend']}\n"
        f"- 요일별 평균: {s['weekday_average']} (최다 요일: {s['best_weekday']})"
    )
