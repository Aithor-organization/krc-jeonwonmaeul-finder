# 전원마을 파인더 — TASKS (DAG)

> `(depends on T###)` = 선행 의존. 동일 wave = 병렬 가능.

## Wave 0 — 계획
- [x] T001 spec.md 작성
- [x] T002 plan.md 작성
- [x] T003 tasks.md 작성

## Wave 1 — 백엔드 코어 (메인, 순차 인터페이스 확정)
- [ ] T010 models.py (Pydantic 스키마) — 계약 고정
- [ ] T011 config.py (sample-mode, allowlist) (depends on T010)
- [ ] T012 guards.py (PII/injection/SSRF) (depends on T010)
- [ ] T013 intent.py (결정론 파서) (depends on T010)
- [ ] T014 clients.py (API+샘플 fallback) (depends on T010, T011)
- [ ] T015 scoring.py (점수, 물 제외) (depends on T010)
- [ ] T016 evidence.py (바인딩/차단) (depends on T010)
- [ ] T017 orchestrator.py (파이프라인) (depends on T012,T013,T014,T015,T016)
- [ ] T018 main.py (FastAPI+static) (depends on T017)

## Wave 1b — 데이터/프론트 (병렬)
- [ ] T020 샘플 데이터 3종 JSON (depends on T010)
- [ ] T021 프론트 3화면 (depends on T010 계약) — 서브에이전트 위임

## Wave 2 — 검증
- [ ] T030 requirements.txt + venv 설치 (depends on T018)
- [ ] T031 pytest 테스트 작성 (depends on T018,T020)
- [ ] T032 eval 테스트셋 30문항 (depends on T013)
- [ ] T033 pytest 전체 통과 (depends on T031,T032)
- [ ] T034 uvicorn 기동 + curl /api/health,/api/search (depends on T033)

## Wave 3 — 리뷰/마감
- [ ] T040 code-reviewer 독립 검토 + 수정 (depends on T034)
- [ ] T041 Codex 적대적 리뷰 + 수정 (depends on T034)
- [ ] T042 app/README(run/deploy) (depends on T034)
- [ ] T043 로컬 git init + commit (depends on T040,T041,T042)

## 완료 정의 (Definition of Done)
AC1~AC12 전부 충족 + pytest 통과 + uvicorn 기동 + curl 성공 + 리뷰 반영. (실 외부배포는 제외 — deploy-ready까지)
