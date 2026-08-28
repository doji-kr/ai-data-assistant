# 나만의 AI 비서 — 스팀 인디게임 리뷰 시계열

내 데이터를 아는 AI 비서. NAS 에서 매일 수집 중인 **스팀 인디게임 신규 리뷰 수(일 단위, 180일)**
시계열을 저장·요약하고, 그 요약을 시스템 프롬프트에 주입해 GPT 가 "내 상황을 아는" 답을 하게 한다.

## 무엇을 해결하나

일반 챗봇은 "요즘 인디게임 리뷰가 어때?"에 일반론만 답한다. 이 서비스는
`/api/data/summary` 가 만든 요약(기간·통계·이동평균·추세·요일 패턴)을 매 대화마다
시스템 프롬프트에 주입하므로, "최근 추세는? 최고점은 언제?" 에 **내 데이터의 수치로** 답한다.

## 기술 스택

- **백엔드**: FastAPI + Pydantic (라우터/서비스 분리, 요청 검증) · Swagger `/docs`
- **DB**: Firebase Firestore (`data`, `conversations` 컬렉션) — 키가 없으면 로컬 JSON 저장소로 자동 폴백
- **AI**: GPT API (OpenAI 호환 — Codyssey 게이트웨이 지원, Function Calling 1종 포함)
- **프론트엔드**: 바닐라 HTML/CSS/JS (채팅 + 로딩 표시 · CRUD · 대화 기록 불러오기 · 요약 카드 ·
  캔버스 차트(원계열+7일 이동평균) · CSV 내보내기 · 다크 모드)
- **컨테이너**: Dockerfile + docker-compose (NAS 데모 배포)

## 데이터

- **출처**: 자체 수집기 indiepulse (Steam 공식 리뷰 API를 매일 폴링, SQLite 저장).
  추출 스크립트: [scripts/seed_from_indiepulse.py](scripts/seed_from_indiepulse.py)
- **정의**: 추적 중인 스팀 게임 전체의 일일 신규 리뷰 수. memo 에 그날 최다 리뷰 게임과 긍정 비율
- **규모**: 180 포인트 (2026-02-08 ~ 2026-08-27) → `data/seed.json`. 저장소가 비어 있으면 부팅 시 자동 적재
- **라이선스 주의**: Steam 리뷰 수는 공개 집계값만 사용하며 리뷰 본문은 포함하지 않는다
- **한계**: 수집기가 게임당 최근 50건까지만 리뷰를 당기므로 과거로 갈수록 표본이 얇다.
  최근 구간의 급증에는 이 수집 편향이 섞여 있어 "추세 상승" 판정은 최근 4주 비교로만 한다

## 시계열 분석 (요약 API 가 수행)

1. **기본 통계** — 합계·평균·최대·최소·표준편차, 최고점(날짜+메모)
2. **7일 이동평균** — 노이즈를 걷어낸 현재 수준
3. **구간 비교 변화율** — 최근 14일 vs 직전 14일 평균으로 상승/하락/유지 판정 (±10% 기준)
4. **요일별 집계** — 요일 패턴과 최다 요일

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/data` | 데이터 추가 (date, value, memo) |
| GET | `/api/data` | 목록 조회 |
| PUT | `/api/data/{id}` | 수정 |
| DELETE | `/api/data/{id}` | 삭제 |
| GET | `/api/data/summary` | 요약 (프롬프트 주입용) |
| GET | `/api/data/export.csv` | CSV 내보내기 |
| POST | `/api/chat` | 요약 주입 → GPT 호출 → 대화 자동 저장 |
| POST | `/api/conversations` | 대화 저장 |
| GET | `/api/conversations` | 대화 목록 (messages 미포함, `message_count` 만) |
| GET | `/api/conversations/{id}` | 특정 대화 전체 messages 조회 (불러오기) |
| DELETE | `/api/conversations/{id}` | 대화 삭제 |
| GET | `/api/report` | 분석 리포트 원문(Markdown) — 프론트가 같은 페이지에서 렌더링 |
| GET | `/api/report.md` | 리포트 md 파일 다운로드 |
| GET | `/api/health` | 상태 (저장소 종류·LLM 설정 여부) |

## 챗 동작 흐름 (컨텍스트 주입 + 도구 호출)

```
사용자 질문 → 요약 계산(compute_summary) → 시스템 프롬프트에 주입
  → GPT 호출 (tools: get_recent_data 제시)
  → (모델이 원본 수치가 필요하다고 판단하면) get_recent_data(days) 호출 → 재호출
  → 답변 반환 + conversations 에 자동 저장
```

도구 호출 근거는 응답의 `used_tools` 로 확인할 수 있고 프론트 하단에 표시된다.
(게이트웨이가 `tool_choice` 강제를 지원하지 않아 도구는 "제시"만 한다 — 호출 여부는 모델 판단.)

## 배포 URL

- **백엔드 API (Render)**: https://ai-data-assistant-3srn.onrender.com
- **Swagger**: https://ai-data-assistant-3srn.onrender.com/docs
- **프론트/대시보드**: 같은 URL에서 서빙 (Vercel 분리 배포 시 vercel.app 도메인 추가)
- **저장소**: https://github.com/doji-kr/ai-data-assistant
- ⚠️ Render 무료 티어는 15분 무접속 시 슬립 — 첫 요청이 30초+ 걸릴 수 있다.
  프론트의 "생각 중…" 로딩 표시가 그 대기를 안내한다

## 대시보드 탐색 (분석 결과 서비스화)

메인 화면의 차트에서 **기간(전체/최근 90일/최근 30일)**과 **집계 단위(일/주)**를 바꿔가며
탐색할 수 있다. 시나리오 예:

1. `전체 × 일` — 7월 중순의 급증(관측 개시 효과)이 전체 스케일을 지배하는 것을 확인
2. `최근 30일 × 일` — 안정 구간만 확대: 8/22 최고점과 주말 상승·화수 하락 패턴이 보인다
3. `전체 × 주` — 주간 합계로 바꾸면 요일 노이즈가 사라지고 성장 감속(W32→W34)이 드러난다

집계 단위를 바꾸면 같은 데이터가 다르게 읽히는 것(일=요일 패턴, 주=추세)이 이 컨트롤의 목적이다.

## 로컬 실행

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env      # 키 채우기 (없으면 챗만 503, 나머지는 동작)
set -a; source .env; set +a
.venv/bin/uvicorn backend.main:app --reload
# → http://localhost:8000 (프론트) · http://localhost:8000/docs (Swagger)
```

## 컨테이너 (NAS 데모)

```bash
cp .env.example .env      # 최소 OPENAI_API_KEY
docker compose up -d --build
# → http://<NAS>:3030 · /docs
```

## 환경 변수 (최소 세트)

| 이름 | 설명 |
|---|---|
| `OPENAI_API_KEY` | GPT API 키 (없으면 챗 엔드포인트만 503) |
| `OPENAI_BASE_URL` | OpenAI 호환 게이트웨이 주소 (기본: Codyssey copa) |
| `OPENAI_MODEL` / `OPENAI_MAX_TOKENS` | 모델·토큰 상한 (비용 가드) |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | 서비스 계정 JSON 경로 또는 문자열. 비우면 로컬 JSON 저장소 |
| `ALLOWED_ORIGINS` | CORS 허용 도메인 (콤마 구분, 기본 `*`) |

## 배포 (Render / Vercel)

- **Render(백엔드)**: 이 저장소를 GitHub 에 푸시 → Web Service 생성 →
  Build `pip install -r backend/requirements.txt` · Start `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
  → 환경 변수 위 표대로 설정 (`ALLOWED_ORIGINS` 에 Vercel 도메인).
  무료 티어는 슬립 후 첫 요청이 30초+ 걸릴 수 있다 — 프론트 로딩 표시("생각 중…")가 그 대기를 안내한다.
- **Vercel(프론트)**: `frontend/` 를 정적 배포하고 `index.html` 의 `window.API_BASE_URL` 에
  Render 백엔드 URL 을 넣는다 (또는 빌드 환경변수로 치환).

## AI 사용 로그 (과제 의무 항목)

1. **사용 작업**: 백엔드/프론트 코드 작성, 시계열 요약 로직 설계, 문서 작성 전반을
   Claude Code (Fable 5) 로 수행. 런타임 챗 기능은 GPT API 사용
2. **사용 이유**: 반복 코드(CRUD·프론트) 시간 절감 + 시계열 기법 선택지 탐색
3. **검증 방법**: 전 엔드포인트 curl 실측(정상·검증 실패·404·503 경로), 요약 수치는
   원본 SQLite 를 별도 쿼리로 대조, 프론트는 브라우저 실행으로 확인. 최종 판단
   (추세 판정 기준 ±10%, 수집 편향 한계 명시)은 사람이 근거를 들어 확정
