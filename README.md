# 전원마을 파인더 (KRC Jeonwonmaeul Finder)

> 제3회 KRC 인공지능 디지털 혁신 공모전 · 서비스개발 부문
> **"지금 실제로 분양 가능한 전원마을을, 공공데이터 근거와 함께 한 화면에서 찾아준다."**

[![GitHub](https://img.shields.io/badge/GitHub-Aithor--organization%2Fkrc--jeonwonmaeul--finder-181717?logo=github&logoColor=white)](https://github.com/Aithor-organization/krc-jeonwonmaeul-finder)
![Visibility](https://img.shields.io/badge/repo-private-red?logo=github&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)
![Tests](https://img.shields.io/badge/tests-38%20passed%20%C2%B7%201%20skipped-brightgreen)
![Status](https://img.shields.io/badge/status-MVP-orange)
![Data](https://img.shields.io/badge/KRC%20OpenAPI-3%20datasets-2f855a)

**저장소**: <https://github.com/Aithor-organization/krc-jeonwonmaeul-finder> (🔒 Private)

---

## 🎯 목적 (Why)

귀농·귀촌을 준비하는 사람은 **"어느 마을로 갈지"**보다 **"지금 실제로 들어갈 수 있는 곳이 어디인지"**를 확인하기가 더 어렵습니다. 분양 진행 상황·마을 기본정보·지역 여건이 서로 다른 사이트에 흩어져 있기 때문입니다.

전원마을 파인더는 한국농어촌공사(KRC)가 공공데이터포털에 개방한 데이터를 **실시간으로 호출**해, 조건에 맞는 **"지금 분양 가능한 전원마을"**을 **근거와 함께** 찾아줍니다. 핵심 원칙은 세 가지입니다.

- **추천이 아니라 사실**: 분양 진행단계·분양율 등 **확정 데이터**로 답한다 (추측 최소화).
- **AI는 대신 결정하지 않는다**: 자연어 해석·설명만 돕고, 사용한 데이터 필드와 근거를 투명하게 보여준다.
- **공공 가치**: KRC가 이미 개방한 데이터의 **대민 활용도**를 높인다 (KRC 미션 — 농어촌 공간 개발·귀농귀촌 정착지원).

> 직전 회차 최우수작 '씨앗톡'(귀농 만능 추천)과의 차별점 = **"어디로 갈지"가 아니라 "지금 들어갈 수 있는 곳"을 실시간 확정 데이터로** 답한다는 것.

---

## ✨ 주요 기능 (Features)

| 기능 | 설명 |
|---|---|
| 🔎 **자연어 조건 검색** | "충남, 예산 2억, 분양 진행 중인 조용한 전원마을" 같은 문장을 구조화 조건으로 파싱 |
| 🏡 **Top N 지구 추천** | KRC 전원마을 분양정보 실시간 조회 → 적합도순 Top 3 카드 (진행단계·분양율·계획세대수) |
| 🌾 **지역 농업가뭄 참고 패널** | 논가뭄지도의 시군 가뭄단계를 **참고 정보로만** 표시 (마을 점수와 분리) |
| 🧾 **근거 리포트** | 추천마다 사용한 API·응답 필드·데이터 기준일·신뢰도 등급 노출 (환각 방지) |
| 🎚️ **데이터 신뢰도 등급 (A~D)** | 매칭 방식 투명 표시, 부족 데이터는 "확인 불가" + 점수 제외 |
| 🛡️ **입력·출력 가드** | PII(주민번호/연락처/이메일) 마스킹 + prompt injection 차단 + 외부호출 allowlist(SSRF) |
| 🤖 **LLM 모델 라우팅 (선택)** | 질의 복잡도별 3-티어: `gpt-5.4-nano` / `gpt-5.4-mini` / `gpt-5.6-luna`, 실패 시 규칙 파서 자동 폴백 |
| 🔌 **키 없이 실행 (sample-mode)** | 공공데이터 활용신청 전에도 샘플 데이터로 전체 플로우 동작 (발표·오프라인 백업) |

**화면 (3-view SPA)**: ① 조건 입력 → ② Top 3 카드(+가뭄 패널) → ③ 근거 리포트 모달.

---

## ⚙️ 작동 원리 (How it works)

### 파이프라인
```
요청
 → [Input Guard]   PII 마스킹 + injection 차단
 → [Intent Parser] 자연어 → 구조화 조건 (규칙 기반 / 선택적 LLM 라우팅)
 → [Data Layer]    KRC API 3종 조회 (+ 샘플 fallback)
 → [Scoring]       적합도 점수 (결정론, 물 정보 제외)
 → [Evidence]      모든 수치를 API 필드에 바인딩 (미바인딩 차단)
 → [Drought Panel] 시군 가뭄단계 (점수와 분리)
 → [Output Guard]  출력 정제 + "참고정보·최종확인 필요" 고지
응답 (Top N + 근거 + 가뭄 패널 + 고지)
```

### 설계 철학
- **결정론 우선, AI 최소**: 점수·조회·필터·검증은 전부 결정론적 코드. LLM은 자연어 파싱·설명 생성만 → 환각 표면 최소화 + 키 없이 테스트 가능.
- **물 정보 점수 분리**: 저수율/가뭄단계는 마을 추천 점수에 넣지 않고 **시군 참고 패널**로만. ("같은 시군 저수율 = 그 마을 물 사정"이라는 인과 오류 회피 — Codex 교차검증 반영.)
- **환각 0 (Evidence Binding)**: 응답의 모든 수치를 원천 API 필드에 바인딩하고, 바인딩 안 되는 값은 출력하지 않는다.
- **프라이버시**: 무저장 기본. LLM 호출 시에도 PII는 guard가 먼저 마스킹한 뒤 전송. 키는 코드/커밋에 두지 않고 파일·환경변수에서 런타임 로드.

### 데이터 (KRC OpenAPI 3종 + 1 선택)
| API | data.go.kr | 역할 |
|---|---|---|
| 전원마을 분양정보 | 15104395 | 🟢 핵심 — 진행단계·분양율·계획세대수 |
| 농촌마을현황 | 15104291 | 보조 — 인구·빈집·자원 |
| 논가뭄지도 | 15117185 | 지역 가뭄 패널 (시군 가뭄단계) |
| 저수지 수위정보 | 15099919 | (선택) 실시간 저수율 |

---

## 🚀 실행 (Quick Start)

```bash
cd app/backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH="$(pwd)" .venv/bin/python -m pytest tests -q      # 테스트 38 passed
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000      # http://127.0.0.1:8000
```
- 검색: `POST /api/search {"query":"충남 예산 2억 분양 진행 중인 조용한 마을"}`
- LLM 모델 라우팅 활성: `export USE_LLM=1` (상세: [`app/README.md`](app/README.md))

---

## 📁 프로젝트 구조

```
app/backend/    FastAPI — models·config·guards·intent·llm_intent·clients·scoring·evidence·orchestrator·main
                + data/samples (3 API 샘플) + tests (38 passed / 1 skipped)
app/frontend/   정적 3화면 SPA (index.html·style.css·app.js, 외부 CDN 없음)
```

## 📚 문서
| 파일 | 성격 |
|---|---|
| [`MVP제안서.md`](MVP제안서.md) | 심사·발표용 요약 (문제/솔루션/가치, 프레임워크명 비노출) |
| [`기술명세서.md`](기술명세서.md) | 내부 빌드 설계도 (아키텍처/데이터/AI/검증/보안/평가) |
| [`spec.md`](spec.md) · [`plan.md`](plan.md) · [`tasks.md`](tasks.md) | 요구사항(AC)·아키텍처·태스크 DAG |
| [`app/README.md`](app/README.md) | 실행·모드·LLM 라우팅 상세 |

> 상위 전략(부모 폴더): `한국농어촌공사대회_우승전략_심화재설계_v3.md` (Codex 교차검증 반영 최종)

---

## 🛣️ 추가로 더 작업할 내용 (Roadmap)

### P0 — 실데이터 연결 (제출 전 필수)
- [ ] **공공데이터 활용신청 승인** 후 `KRC_SERVICE_KEY` 연결 → `clients.py` **live-mode 실호출** 구현 (현재 sample-mode만 동작)
- [ ] 저수지 수위 API `county` 조회키·오퍼레이션명 **실호출 확정** (현재 [미확인])
- [ ] 공모전 **공식 신청서·배점표** 확보 → 문서/우선순위 정합

### P1 — 정확도·완성도
- [ ] **시군구(sigungu) 파싱** 강화 (현재 규칙 파서는 시도 단위, sigungu는 LLM만 처리)
- [ ] 프론트 **브라우저 실제 렌더 검증** (현재 API 계약·정적 서빙만 확인)
- [ ] 지도 시각화 (지구 위치 + 인근 저수지 표시)
- [ ] 파싱 정확도 테스트셋 확대(30→100문항) + 규칙 vs LLM **baseline 비교표** (AI 필요성 증빙)

### P2 — 신뢰성·운영
- [ ] **CI 파이프라인** (GitHub Actions: pytest + lint 품질 게이트)
- [ ] 관측성 화면 (API 호출 성공/실패 로그·응답시간·fallback — 발표 백오피스 1장)
- [ ] LLM 라우팅 기준 튜닝 (현재 토큰수/조건수 휴리스틱 → 실측 기반 조정)
- [ ] 개인정보·저작권 자산대장 문서화 (데이터별 이용조건)

### P3 — 확장
- [ ] **프라이버시 모드**: 자연어 파싱을 로컬 소형 모델(MiniCPM5-1B/Ollama)로 전환 → 외부 전송 0
- [ ] KRC 다른 개방 데이터셋(지역개발사업 등) 모듈 추가
- [ ] 귀농 지원정책·자금 정보 연동
- [ ] 발표용 1분 데모 영상 + 국민투표용 카드뉴스

### 배포
- [ ] 프론트 정적 호스팅 + 백엔드 컨테이너/서버리스 (deploy-ready 상태, **실제 외부 배포는 승인 후**)

---

## 🧩 참조 시스템 (패턴 경량 이식 — 기술명세서 §12)
- **AITHOR-Agent-Framework** — kernel(파이프라인)·verifier/evidence(근거 바인딩)·guard(PII/injection/SSRF)·routing(tier) 패턴
- **minicpm5-poc** — 로컬 NL→JSON 파서 (프라이버시 모드 후보)
- **AI-research-SKILLs** — instructor(구조화 출력)·langgraph·guardrails·promptfoo

> ⚠️ 배점표·투표 반영비율·`county` 조회키·씨앗톡 실물 기능은 [미확인] — 제출 전 공식 확인 필수. 실 KRC API 미연결(sample-mode), 실제 외부 배포 미실행(deploy-ready까지).
