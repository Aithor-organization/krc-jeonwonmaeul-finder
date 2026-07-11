# 전원마을 파인더 — PLAN (아키텍처 + 기술 결정 + 마일스톤)

## P1. 스택 결정
| 계층 | 선택 | 근거 |
|---|---|---|
| 백엔드 | Python 3.12 + FastAPI + Uvicorn | 기술명세 §8, 참조 시스템(Python) 일관 |
| 검증 | Pydantic v2 | 구조화 스키마 강제 |
| HTTP | httpx (타임아웃 5s) | 실 API 연동(키 확보 시) |
| 파싱 | **결정론 규칙 엔진**(정규식/사전) | 키 없이 동작·완전 테스트·환각 0 (LLM은 선택 어댑터) |
| 프론트 | 정적 HTML/CSS/JS (빌드 없음) | 실행 견고성(npm 빌드 취약성 회피), FastAPI static 서빙 |
| 테스트 | pytest | AC 검증 |

## P2. 모듈 구조 (파일 소유권 — 병렬 충돌 방지)
```
app/backend/
  config.py        # 설정, sample-mode 플래그, allowlist 호스트
  models.py        # Pydantic 스키마 (요청/응답/도메인)
  guards.py        # Input/Output Guard (PII, injection, SSRF allowlist)
  intent.py        # 결정론 자연어 파서 (region/budget/stage/preference)
  clients.py       # KRC API 클라이언트 + 샘플 fallback (3종)
  scoring.py       # 적합도 점수 (물 제외) + 신뢰도 등급
  evidence.py      # Evidence 바인딩 + 미바인딩 차단
  orchestrator.py  # 파이프라인 조립 (guard→parse→fetch→score→evidence→report)
  main.py          # FastAPI 앱 + 엔드포인트 + static 서빙
  data/samples/    # 3 API 샘플 응답 JSON
  tests/           # pytest
app/frontend/      # index.html, app.js, style.css
```

## P3. 파이프라인 (기술명세 §2.1 경량 이식)
```
요청 → [InputGuard] → [IntentParser] → [DataOrchestrator(clients+cache)]
     → [Scoring(물 제외)] → [EvidenceBinder] → [OutputGuard(고지)] → 응답
```

## P4. 팀 구성 & 위임 (context:fork)
| 역할 | 담당 | 산출 |
|---|---|---|
| Coordinator/Integrator | 메인(Opus) | 인터페이스 확정·백엔드 코어·통합·검증 |
| Builder-Frontend | 서브에이전트(opus) | 정적 3화면(고정 API 계약) |
| Reviewer | code-reviewer(opus) + Codex(적대적) | 독립 검토 |

> 품질 우선(Rule 2): 통합·인터페이스·디버깅은 메인. 격리 가능한 프론트만 병렬 위임. API 계약을 먼저 고정해 LP-1402(계약 실패) 회피.

## P5. 마일스톤 (본 세션)
1. 계획 문서(spec/plan/tasks) ✅
2. 백엔드 코어 구현 (models→guards→intent→clients→scoring→evidence→orchestrator→main)
3. 샘플 데이터 + 프론트(병렬)
4. 테스트 작성 + venv 설치 + `pytest` 통과
5. 서버 기동 + `/api/health`·`/api/search` curl 검증
6. 독립 리뷰(code-reviewer + Codex) + 수정
7. 로컬 git commit + 배포 가이드 (실 외부배포 전 정지)

## P6. 배포 경계 (Rule 6-4)
- deploy-**ready**까지 자율: 빌드/테스트/실행 검증, 로컬 커밋, 배포 문서.
- deploy-**execute**(외부 push/publish)는 하드 게이트 → 사용자 승인 전까지 미실행.
