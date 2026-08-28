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

    # 트렌드 제거 계절성: 중심 7일 이동평균을 빼고 요일별 편차를 본다.
    # 원시 요일 평균은 상승/하락 트렌드에 교란되므로(리포트 4-4) 이 값을 함께 준다.
    # 창은 최근 8주(56일)로 제한한다 — 먼 과거 구간(수집 개시 전 등)이 편차를 희석하지 않게.
    seasonality = None
    if len(values) >= 28:
        w_rows, w_vals = rows[-56:], values[-56:]
        pool: dict[int, list[float]] = {}
        for i in range(3, len(w_rows) - 3):
            t = statistics.mean(w_vals[i - 3: i + 4])
            try:
                wd = dt.date.fromisoformat(w_rows[i]["date"]).weekday()
            except ValueError:
                continue
            pool.setdefault(wd, []).append(w_vals[i] - t)
        seasonality = {WEEKDAYS[k]: round(statistics.mean(v), 1) for k, v in sorted(pool.items()) if v}

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
        "weekday_seasonality_detrended": seasonality,
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
        f"- 요일별 평균(원시, 트렌드에 교란된 값): {s['weekday_average']}"
        + _seasonality_lines(s.get("weekday_seasonality_detrended"))
    )


def _seasonality_lines(sea: dict | None) -> str:
    if not sea:
        return ""
    lo, hi = min(sea, key=sea.get), max(sea, key=sea.get)
    return (
        f"\n- 요일별 계절성(트렌드 제거 편차, 최근 8주): {sea}\n"
        f"- ★ 요일 비교 질문에는 계절성 기준으로 답할 것 — "
        f"가장 적은 요일: {lo}({sea[lo]}) · 가장 많은 요일: {hi}(+{sea[hi]})"
    )
