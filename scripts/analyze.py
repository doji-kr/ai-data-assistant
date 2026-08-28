"""시계열 분석 + 시각화 — REPORT.md 의 그림과 수치를 재현하는 단일 스크립트.

실행: .venv/bin/python scripts/analyze.py   (저장소 루트에서)
입력: data/seed.json  ·  출력: images/*.png + 표준출력의 수치(리포트 인용값)

집계 단위 근거: 원계열은 「일」 단위로 그대로 두되(급증 구간 위치 확인),
추세 판정은 노이즈가 커서 7일 이동평균과 주간 합계로 본다 — 리뷰 유입은
주말 효과가 있어 7의 배수 창이 요일 편향을 상쇄한다.
"""
import json
import os
import statistics
import sys
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 한글 폰트 (없으면 기본 폰트로 진행)
for cand in ("scripts/Pretendard.ttf", "/tmp/Pretendard.ttf",
             os.environ.get("KR_FONT", "")):
    if cand and os.path.exists(cand):
        font_manager.fontManager.addfont(cand)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=cand).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

rows = sorted(json.load(open("data/seed.json", encoding="utf-8")), key=lambda r: r["date"])
dates = [date.fromisoformat(r["date"]) for r in rows]
vals = [float(r["value"]) for r in rows]
os.makedirs("images", exist_ok=True)

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def ma(xs, w):
    return [statistics.mean(xs[max(0, i - w + 1): i + 1]) for i in range(len(xs))]


# ── 그림 1: 일일 리뷰 수 + 7일 이동평균 ─────────────────────────────
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(dates, vals, lw=0.8, alpha=0.45, label="일일 신규 리뷰 수")
ax.plot(dates, ma(vals, 7), lw=2, label="7일 이동평균")
peak_i = vals.index(max(vals))
ax.annotate(f"{dates[peak_i]} · {int(vals[peak_i])}건",
            (dates[peak_i], vals[peak_i]), xytext=(-130, -6),
            textcoords="offset points", arrowprops={"arrowstyle": "->"})
ax.set_title("스팀 인디게임 일일 신규 리뷰 수 (180일)")
ax.set_ylabel("건")
ax.legend()
fig.tight_layout()
fig.savefig("images/01_daily_ma7.png", dpi=110)

# ── 그림 2: 주간 합계 + 주간 변화율 ────────────────────────────────
weeks, wsum = [], []
for d, v in zip(dates, vals):
    wk = d.isocalendar()[:2]
    if weeks and weeks[-1] == wk:
        wsum[-1] += v
    else:
        weeks.append(wk)
        wsum.append(v)
wlab = [f"{y}-W{w:02d}" for y, w in weeks]
chg = [None] + [round((b - a) / a * 100, 1) if a else None for a, b in zip(wsum, wsum[1:])]
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.5), sharex=True,
                               height_ratios=[2, 1])
ax1.bar(range(len(wsum)), wsum)
ax1.set_title("주간 리뷰 합계와 주간 변화율")
ax1.set_ylabel("주간 합계(건)")
ax2.axhline(0, color="gray", lw=0.8)
ax2.bar(range(len(chg)), [c or 0 for c in chg],
        color=["#c44" if (c or 0) < 0 else "#48a" for c in chg])
ax2.set_ylabel("전주 대비 %")
step = max(1, len(wlab) // 10)
ax2.set_xticks(range(0, len(wlab), step), wlab[::step], rotation=45, ha="right")
fig.tight_layout()
fig.savefig("images/02_weekly_change.png", dpi=110)

# ── 그림 3: 요일별 평균 ────────────────────────────────────────────
by_wd = {i: [] for i in range(7)}
for d, v in zip(dates, vals):
    by_wd[d.weekday()].append(v)
avg = [statistics.mean(by_wd[i]) for i in range(7)]
fig, ax = plt.subplots(figsize=(7, 3.6))
bars = ax.bar(WEEKDAYS, avg)
bars[avg.index(max(avg))].set_color("#e0730f")
ax.set_title("요일별 평균 신규 리뷰 수")
ax.set_ylabel("건")
fig.tight_layout()
fig.savefig("images/03_weekday.png", dpi=110)

# ── 그림 4: 시계열 분해 (안정 구간, 가법 모형) ─────────────────────
# 관측 개시 효과가 섞인 전 기간 대신 수집이 안정된 2026-07-19 이후만 분해한다.
# 트렌드 = 중심 7일 이동평균 · 계절성 = 요일별 (값-트렌드) 평균 · 잔차 = 나머지
STABLE = date(2026, 7, 19)
# 마지막 날은 수집이 하루치를 다 못 담은 부분 관측이라 분해·예측에서 뺀다 (리포트 3절)
sd = [(d, v) for d, v in zip(dates[:-1], vals[:-1]) if d >= STABLE]
s_dates = [d for d, _ in sd]
s_vals = [v for _, v in sd]

trend = [None] * len(s_vals)
for i in range(3, len(s_vals) - 3):
    trend[i] = statistics.mean(s_vals[i - 3: i + 4])
season_pool = {i: [] for i in range(7)}
for d, v, t in zip(s_dates, s_vals, trend):
    if t is not None:
        season_pool[d.weekday()].append(v - t)
seasonal_by_wd = {k: (statistics.mean(v) if v else 0.0) for k, v in season_pool.items()}
seasonal = [seasonal_by_wd[d.weekday()] for d in s_dates]
resid = [v - t - s if t is not None else None
         for v, t, s in zip(s_vals, trend, seasonal)]

fig, axes = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
axes[0].plot(s_dates, s_vals, lw=1)
axes[0].set_ylabel("원계열")
axes[0].set_title("시계열 분해 — 안정 구간(2026-07-19~) · 가법 모형")
axes[1].plot(s_dates, trend, lw=2, color="#e0730f")
axes[1].set_ylabel("트렌드")
axes[2].plot(s_dates, seasonal, lw=1, color="#48a")
axes[2].set_ylabel("계절성(요일)")
axes[3].plot(s_dates, resid, lw=0.8, color="gray")
axes[3].axhline(0, color="black", lw=0.5)
axes[3].set_ylabel("잔차")
fig.tight_layout()
fig.savefig("images/04_decomposition.png", dpi=110)

# ── 그림 5: 베이스라인 예측 (백테스트 + 향후 7일) ──────────────────
# 방법: 예측 = 최근 7일 트레일링 평균(수준) + 요일 계절성. 대조군: naive(마지막 값 유지).
# 백테스트: 마지막 7일을 떼어내고, 그 이전 데이터만으로 같은 방법을 적용해 MAE 비교.
def forecast(train_dates, train_vals, horizon_dates):
    level = statistics.mean(train_vals[-7:])
    t7 = [None] * len(train_vals)
    for i in range(3, len(train_vals) - 3):
        t7[i] = statistics.mean(train_vals[i - 3: i + 4])
    pool = {i: [] for i in range(7)}
    for d, v, t in zip(train_dates, train_vals, t7):
        if t is not None:
            pool[d.weekday()].append(v - t)
    sea = {k: (statistics.mean(v) if v else 0.0) for k, v in pool.items()}
    return [max(0.0, level + sea[d.weekday()]) for d in horizon_dates]

hold_d, hold_v = s_dates[-7:], s_vals[-7:]
bt = forecast(s_dates[:-7], s_vals[:-7], hold_d)
mae_model = statistics.mean(abs(a - b) for a, b in zip(bt, hold_v))
mae_naive = statistics.mean(abs(s_vals[-8] - b) for b in hold_v)

from datetime import timedelta
future_d = [s_dates[-1] + timedelta(days=i) for i in range(1, 8)]
future_v = forecast(s_dates, s_vals, future_d)

fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(s_dates[-28:], s_vals[-28:], lw=1.2, label="실측")
ax.plot(hold_d, bt, "o--", lw=1.5, color="#48a",
        label=f"백테스트 예측 (MAE {mae_model:.0f}건)")
ax.plot(future_d, future_v, "s--", lw=1.5, color="#e0730f", label="향후 7일 예측")
ax.axvline(s_dates[-1], color="gray", lw=0.7, ls=":")
ax.set_title("베이스라인 예측 — 수준(7일 평균) + 요일 계절성")
ax.set_ylabel("건")
ax.legend()
fig.tight_layout()
fig.savefig("images/05_forecast.png", dpi=110)

# ── 리포트 인용 수치 ───────────────────────────────────────────────
half = len(vals) // 2
print(f"기간 {dates[0]} ~ {dates[-1]} · {len(vals)}일 · 합계 {sum(vals):.0f}건")
print(f"평균 {statistics.mean(vals):.1f} · 중앙값 {statistics.median(vals):.0f} · 표준편차 {statistics.pstdev(vals):.1f}")
print(f"전반 90일 평균 {statistics.mean(vals[:half]):.1f} vs 후반 90일 평균 {statistics.mean(vals[half:]):.1f}")
print(f"최고점 {dates[peak_i]} {int(vals[peak_i])}건 — {rows[peak_i]['memo']}")
print(f"최근 14일 평균 {statistics.mean(vals[-14:]):.1f} vs 직전 14일 {statistics.mean(vals[-28:-14]):.1f}")
top_weeks = sorted(zip(wlab, wsum), key=lambda t: -t[1])[:3]
print("주간 합계 상위:", top_weeks)
print("요일 평균:", {w: round(a, 1) for w, a in zip(WEEKDAYS, avg)})
print("분해 계절성(요일별 편차):", {WEEKDAYS[k]: round(v, 1) for k, v in seasonal_by_wd.items()})
print(f"백테스트 MAE — 모델 {mae_model:.0f}건 vs naive {mae_naive:.0f}건")
print("향후 7일 예측:", [(d.isoformat(), round(v)) for d, v in zip(future_d, future_v)])
sys.stderr.write("images/*.png 5장 저장 완료\n")
