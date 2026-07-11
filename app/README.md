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
