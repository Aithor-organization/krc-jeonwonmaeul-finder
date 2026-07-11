# 전원마을 파인더 — 실행 가이드

KRC 공공데이터 기반 "분양 가능한 전원마을" 실시간 검색 서비스. **키 없이 sample-mode로 즉시 실행** 가능.

## 요구사항
- Python 3.11+ (검증: 3.12), Node 불필요(프론트는 정적 파일).

## 설치 & 실행 (로컬)
```bash
cd app/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 테스트 (25개)
PYTHONPATH="$(pwd)" .venv/bin/python -m pytest tests -q

# 서버 기동 (프론트 포함)
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```
- 브라우저: http://127.0.0.1:8000  (조건 입력 → Top 3 → 근거 리포트)
- 헬스체크: `GET /api/health`
- 검색: `POST /api/search  {"query":"충남 예산 2억 분양 진행 중인 조용한 마을"}`

## 모드
- **sample-mode (기본)**: `KRC_SERVICE_KEY` 미설정 시 `data/samples/*.json`로 동작 (오프라인·발표 백업).
- **live-mode**: 공공데이터포털 활용신청 승인 후 `export KRC_SERVICE_KEY=...` → `clients.py`의 live 경로 활성화(엔드포인트 오퍼레이션명·`county` 파라미터는 실호출로 확정 필요 — 기술명세 §14).

## LLM 자연어 파서 모델 라우팅 (선택)
기본은 결정론 규칙 파서(키 불필요). `USE_LLM=1` 설정 시 OpenAI 모델로 파싱하며 **질의 복잡도에 따라 3개 티어로 라우팅**:
- simple → `gpt-5.4-nano` · medium → `gpt-5.4-mini` · complex → `gpt-5.6-luna`

```bash
export USE_LLM=1                     # LLM 파서 활성
# 키는 코드/커밋에 두지 않음 — 파일 또는 환경에서 런타임 로드:
export OPENAI_KEY_FILE=/path/to/keyfile.md   # "openai api key : sk-..." 줄 파싱 (기본값 설정됨)
# 또는  export OPENAI_API_KEY=sk-...
```
- 모델 오버라이드: `LLM_MODEL_SIMPLE`/`LLM_MODEL_MEDIUM`/`LLM_MODEL_COMPLEX` 환경변수.
- **폴백**: LLM 호출 실패 시 자동으로 규칙 파서 사용(무중단). PII는 호출 전 guard가 마스킹.
- 헬스체크(`/api/health`)에 `llm_enabled`·`llm_models` 표시. 라이브 테스트: `USE_LLM=1 pytest tests/test_llm_live.py`.

## 구조
```
app/backend/  models·config·guards·intent·clients·scoring·evidence·orchestrator·main + data/samples + tests
app/frontend/ index.html·style.css·app.js (정적, 외부 CDN 없음)
```

## 배포 (deploy-ready)
- 백엔드: `uvicorn main:app` 컨테이너화 or 서버리스. 환경변수 `KRC_SERVICE_KEY`.
- 프론트: FastAPI가 `/`로 서빙(단일 배포) 또는 정적 호스팅 분리.
- **발표 백업**: 로컬 실행본 + 오프라인 샘플(sample-mode) 기본 내장.
- ⚠️ **실제 외부 배포(프로덕션 push/publish)는 사용자 승인 후 진행** (본 저장소는 deploy-ready까지).

## 검증 상태
- pytest 25/25 통과 · uvicorn 기동 · `/api/health` 200 · `/api/search` 정상 · 프론트 200 (2026-07-11 실측).
- AC1~AC12 충족 (spec.md 참조).
