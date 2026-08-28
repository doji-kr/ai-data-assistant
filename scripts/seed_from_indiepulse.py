"""data/seed.json 생성 스크립트 — 데이터 출처와 수집 방법의 기록.

출처: NAS 의 indiepulse 수집기(SQLite). Steam 리뷰를 매일 수집한다.
  DB: /volume1/docker/sojaeham/indiepulse/data/indiepulse.db (reviews 테이블)
값: 추적 중인 스팀 게임 전체의 「일일 신규 리뷰 수」 (최근 200일 구간)
메모: 그날 리뷰가 가장 많이 달린 게임 + 긍정 비율

주의: 게임당 최근 50건까지만 수집하는 소스라 과거로 갈수록 표본이 얇아진다
(리포트/README 의 한계점 참조). 실행은 DB 가 보이는 NAS 컨테이너 안에서만 가능.
"""
import json
import sqlite3
import sys

DB = "/volume1/docker/sojaeham/indiepulse/data/indiepulse.db"
OUT = "data/seed.json"

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
rows = con.execute("""
SELECT date(r.posted_at) d, COUNT(*) n,
       (SELECT g2.title FROM reviews r2 JOIN games g2 USING(appid)
        WHERE date(r2.posted_at)=date(r.posted_at)
        GROUP BY r2.appid ORDER BY COUNT(*) DESC LIMIT 1) top_game,
       ROUND(AVG(r.voted_up)*100) pos_pct
FROM reviews r
WHERE r.posted_at >= date('now','-200 days')
GROUP BY 1 ORDER BY 1""").fetchall()

seed = [{"date": d, "value": n, "memo": f"최다 리뷰: {top} · 긍정 {int(pos)}%"}
        for d, n, top, pos in rows]
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(seed, f, ensure_ascii=False, indent=1)
print(f"{len(seed)} points -> {OUT}", file=sys.stderr)
