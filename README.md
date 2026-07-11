# 전원마을 파인더 (KRC Jeonwonmaeul Finder)

> 제3회 KRC 인공지능 디지털 혁신 공모전 · 서비스개발 부문
> **"지금 분양 가능한 전원마을을, 공공데이터 근거와 함께 한 화면에서 찾아준다."**

[![GitHub](https://img.shields.io/badge/GitHub-Aithor--organization%2Fkrc--jeonwonmaeul--finder-181717?logo=github&logoColor=white)](https://github.com/Aithor-organization/krc-jeonwonmaeul-finder)
![Visibility](https://img.shields.io/badge/repo-private-red?logo=github&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)
![Tests](https://img.shields.io/badge/tests-40%20passed%20%C2%B7%201%20skipped-brightgreen)
![Status](https://img.shields.io/badge/status-MVP-orange)
![Data](https://img.shields.io/badge/KRC%20OpenAPI-3%20datasets-2f855a)

**저장소**: <https://github.com/Aithor-organization/krc-jeonwonmaeul-finder> (Private)

---

## 현재 화면

![전원마을 파인더 랜딩페이지](docs/images/landing-page.jpg)

첫 화면에서 바로 자연어 검색을 실행할 수 있으며, 현재 데이터 모드를 항상 노출합니다. 위 화면은 공공데이터 활용신청 전에도 전체 흐름을 검증할 수 있는 **sample-mode** 상태입니다.

---

## 목적

귀농·귀촌을 준비하는 사람은 "어느 지역이 좋아 보이는지"보다 **지금 실제로 분양 중인 곳이 어디인지**, 그리고 **그 판단의 근거가 무엇인지** 확인하기 어렵습니다. 분양 진행상황, 마을 기본정보, 지역 참고정보가 서로 다른 데이터에 흩어져 있기 때문입니다.

전원마을 파인더는 다음 한 가지 과업에 집중합니다.

> 사용자의 자연어 조건을 구조화하고, 전원마을 분양정보와 농촌마을현황을 결합해 후보를 좁힌 뒤, 결과에 사용한 API 필드와 값을 함께 보여준다.

현재 MVP는 키 없이 실행 가능한 **sample-mode**로 동작합니다. KRC OpenAPI live-mode는 활용신청 승인과 실제 응답 계약 검증 후 연결할 예정이며, UI와 API는 현재 모드를 숨기지 않습니다.

---

## 핵심 기능

| 기능 | 동작 |
|---|---|
| **검색 중심 랜딩페이지** | 별도 소개 화면을 거치지 않고 첫 화면에서 바로 조건을 입력하고 검색 |
| **자연어 조건 해석** | "충남, 예산 2억, 분양 중인 조용한 마을"에서 지역·예산·분양단계·선호·세대수 추출 |
| **조건 적합 후보 Top 3** | 진행단계, 분양율, 계획세대수와 선호 일치도를 결정론적으로 계산해 정렬 |
| **조건 자동완화 방지** | 요청한 지역·진행단계·최소 세대수에 결과가 없으면 다른 조건의 마을을 임의로 섞지 않음 |
| **근거 리포트** | 카드에 표시한 진행단계·분양율·계획세대수·인구·빈집 수를 원본 API와 필드에 연결 |
| **데이터 신뢰도 A~D** | 법정동코드 직접 매칭 여부 등 데이터 결합 방식에 따라 신뢰도 등급 표시 |
| **가뭄 참고 패널** | 상위 후보 시군의 농업가뭄 단계를 별도 표시하고 추천 점수에서는 제외 |
| **정직한 결측 처리** | 데이터에 없는 분양가 등은 추정하지 않고 "확인 불가" 또는 경고로 안내 |
| **입력·출력 보호** | 주민번호·연락처·이메일 마스킹, prompt injection 차단, 출력 PII 재검사 |
| **선택적 LLM 라우팅** | `USE_LLM=1`일 때 질의 복잡도별 모델을 사용하고 실패 시 규칙 파서로 폴백 |
| **키 없이 실행** | KRC 서비스키가 없어도 샘플 데이터로 검색·점수·근거·UI 전체 흐름 실행 |

사용자 화면은 하나의 SPA 안에서 **조건 입력 → 검색 결과 → 근거 리포트 모달**로 이어집니다.

---

## 시스템 작동 방식

### 전체 요청 흐름

```text
브라우저
  ├─ GET /api/health       현재 sample/live 모드 확인
  └─ POST /api/search      자연어 검색 요청
         ↓
     [Input Guard]         PII 마스킹 + prompt injection 차단
         ↓
     [Intent Parser]       자연어 → 지역/예산/단계/선호/세대수
         ↓
     [Data Client]         분양정보 + 농촌마을현황 + 논가뭄지도 조회
         ↓
     [Filter & Scoring]    조건 필터 + 결정론적 적합도 계산
         ↓
     [Evidence Binding]    노출 수치 → API/필드/값 바인딩
         ↓
     [Drought Panel]       시군 가뭄정보를 점수와 분리
         ↓
     SearchResponse        Top N + 근거 + 경고 + 최종확인 고지
         ↓
브라우저 결과 카드와 근거 모달 렌더링
```

### 단계별 처리

| 단계 | 담당 모듈 | 처리 내용 | 실패·예외 처리 |
|---|---|---|---|
| 1. 모드 확인 | `main.py`, `config.py` | `/api/health`로 sample-mode와 LLM 활성 상태 반환 | 확인 실패 시 프론트에 "데이터 상태 확인 불가" 표시 |
| 2. 입력 보호 | `guards.py` | PII 마스킹, 개행 우회를 포함한 injection 패턴 검사 | 위험한 입력은 검색하지 않고 빈 응답과 차단 사유 반환 |
| 3. 조건 해석 | `intent.py`, `llm_intent.py` | 지역·예산·분양단계·세대수·선호를 `ParsedQuery`로 변환 | LLM 실패 시 규칙 파서 사용, 조건 미인식 시 전체 데이터 노출 금지 |
| 4. 데이터 조회 | `clients.py` | 분양정보 필터링, 법정동코드로 마을현황 결합, 시군 가뭄정보 조회 | 현재는 로컬 샘플 데이터만 사용하며 상태 경고를 응답에 포함 |
| 5. 필터·점수 | `scoring.py` | 진행단계 50%, 분양 가용성 30%, 선호 20%로 적합도 계산 | 잘못된 숫자는 `None` 처리, 진행단계·세대수 조건은 임의 완화하지 않음 |
| 6. 근거 검증 | `evidence.py` | 카드의 모든 수치를 API ID와 원본 필드에 바인딩 | 미바인딩 수치는 경고하고 확정값처럼 노출하지 않음 |
| 7. 응답 조립 | `orchestrator.py` | Top N, 가뭄 패널, 근거, 경고, 고지문을 `SearchResponse`로 조립 | 데이터가 없으면 빈 결과와 다음 검색 안내 반환 |
| 8. 화면 렌더링 | `app.js` | 로딩·성공·빈 결과·오류 상태와 근거 모달 렌더링 | 요청 타임아웃, 재검색, 키보드 모달 닫기, 스크린리더 상태 갱신 지원 |

### 주요 API

| Method | Path | 역할 |
|---|---|---|
| `GET` | `/api/health` | 서버, 데이터 모드, LLM 라우팅 상태 확인 |
| `POST` | `/api/search` | 자연어 또는 구조화 조건으로 전원마을 후보 검색 |
| `GET` | `/api/village/{gu_id}` | 허용된 필드만 포함한 단일 지구 상세 조회 |

`POST /api/search`의 핵심 응답 필드는 다음과 같습니다.

```json
{
  "query_parsed": {"region": {"sido": "충청남도"}, "sale_stage": ["분양중"]},
  "top": [{"gu_name": "홍성 갈산 전원마을", "score": 0.895, "confidence_grade": "A"}],
  "drought_panel": {"sigungu": "홍성군", "drought_stage": "관심"},
  "evidence": [{"api": "15104395", "field": "분양율", "value": 35}],
  "warnings": ["sample-mode: 샘플 데이터로 동작합니다."],
  "disclaimer": "공공데이터 기반 참고정보이며 최종 계약·분양은 공식 기관 확인이 필요합니다."
}
```

---

## 작동 원리와 설계 원칙

### 1. 결정론 우선, AI 최소

필터링, 점수 계산, 데이터 결합, 근거 검증은 모두 코드로 재현 가능하게 처리합니다. LLM은 선택적으로 자연어를 구조화하는 역할만 맡으며 최종 순위를 직접 생성하지 않습니다.

```text
적합도 = 0.5 × 진행단계 + 0.3 × 분양 가용성 + 0.2 × 선호 일치도
```

### 2. Evidence Binding

화면에 노출하는 수치는 `api + field + value` 근거가 있어야 합니다. 카드별 근거는 `evidence.py`가 생성하고 `is_fully_bound()`가 누락 여부를 확인합니다. 데이터에 없는 값은 모델이 보완하지 않습니다.

### 3. 조건을 몰래 완화하지 않음

"분양완료", "100세대 이상"처럼 사용자가 명시한 조건을 만족하는 결과가 없으면 다른 단계나 작은 지구를 대신 보여주지 않습니다. 빈 결과가 잘못된 추천보다 낫다는 원칙입니다.

### 4. 상관관계와 인과관계 분리

시군 단위 가뭄정보는 특정 마을의 물 사정을 증명하지 않습니다. 따라서 가뭄 단계와 평년 대비 수치는 **지역 참고 패널**에만 표시하고 마을 적합도에는 반영하지 않습니다.

### 5. 실패를 숨기지 않음

- sample-mode 여부를 첫 화면과 API 경고에 표시
- 예산 데이터가 없어 필터링하지 못하면 그 사실을 안내
- LLM 실패 시 규칙 파서 사용 여부를 경고에 기록
- 데이터가 없거나 조건을 인식하지 못하면 전체 목록 대신 빈 결과 반환
- 모든 응답에 공식 기관 최종확인 필요 문구 포함

### 6. 개인정보와 외부호출 경계

검색 문장은 기본적으로 저장하지 않습니다. 입력은 파싱 전에 PII를 마스킹하며, 향후 live-mode 외부호출은 `apis.data.go.kr`, `api.data.go.kr` allowlist 안에서만 허용하도록 설계되어 있습니다.

---

## 데이터와 실행 모드

### KRC 데이터셋

| 데이터 | data.go.kr ID | 시스템 역할 | 현재 MVP |
|---|---:|---|---|
| 전원마을 분양정보 | `15104395` | 진행단계·분양율·계획세대수 | 샘플 데이터 |
| 농촌마을현황 | `15104291` | 인구·빈집·지역 자원 | 샘플 데이터 |
| 논가뭄지도 | `15117185` | 시군 농업가뭄 참고 패널 | 샘플 데이터 |
| 저수지 수위정보 | `15099919` | 실시간 저수율 확장 후보 | 미연결 |

### 실행 모드

| 모드 | 상태 | 동작 |
|---|---|---|
| **sample-mode** | 현재 기본값 | `app/backend/data/samples/*.json`으로 전체 검색 흐름 실행 |
| **live-mode** | 구현 예정 | KRC 서비스키, 실제 오퍼레이션명·파라미터·응답 스키마 검증 후 활성화 |
| **LLM parser** | 선택 | `USE_LLM=1`일 때 활성화하며 실패 시 규칙 파서로 자동 폴백 |

현재 `KRC_SERVICE_KEY`를 설정하더라도 `clients.py`의 live 호출 경로가 아직 구현되지 않았으므로 sample-mode가 유지됩니다.

---

## 실행 방법

요구사항은 Python 3.11 이상입니다. 프론트엔드는 정적 HTML/CSS/JavaScript이므로 별도 Node 빌드가 필요하지 않습니다.

```bash
cd app/backend
python -m venv .venv

# 가상환경 활성화 후
python -m pip install -r requirements.txt
python -m pytest tests -q
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

- 웹 화면: <http://127.0.0.1:8000>
- 헬스체크: `GET http://127.0.0.1:8000/api/health`
- 검색 예시:

```bash
curl -X POST http://127.0.0.1:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"충남 예산 2억 분양 중인 조용한 마을"}'
```

LLM 파서를 선택적으로 사용하려면 다음 환경변수를 설정합니다.

```bash
export USE_LLM=1
export OPENAI_API_KEY=...
```

세부 모델 라우팅과 키 파일 설정은 [`app/README.md`](app/README.md)를 참고하세요.

---

## 프로젝트 구조

```text
app/
├─ backend/
│  ├─ main.py              FastAPI 엔드포인트와 정적 프론트 서빙
│  ├─ orchestrator.py      전체 검색 파이프라인 조립
│  ├─ guards.py            PII·injection·SSRF 경계
│  ├─ intent.py            결정론적 자연어 파서
│  ├─ llm_intent.py        선택적 LLM 파서와 폴백
│  ├─ clients.py           KRC 데이터 접근 계층
│  ├─ scoring.py           결정론적 적합도 계산
│  ├─ evidence.py          수치 근거 바인딩
│  ├─ data/samples/        키 없이 실행하는 샘플 데이터
│  └─ tests/               API·보안·파싱·점수·근거·프론트 계약 테스트
└─ frontend/
   ├─ index.html           검색 중심 랜딩 SPA
   ├─ app.js               검색·상태·근거 모달 상호작용
   ├─ style.css            기반 토큰·헤더·히어로
   ├─ results.css          결과 카드·상태·근거 UI
   ├─ sections.css         원리·데이터·푸터·모달
   ├─ responsive.css       태블릿·모바일·저높이 대응
   └─ assets/              랜딩페이지 이미지
```

---

## 검증 상태

- `pytest`: **40 passed, 1 skipped**
- `node --check app/frontend/app.js`: 통과
- FastAPI `/api/health`: 200 OK
- Playwright 실제 검색·빈 결과·오류·근거 모달 검증
- 반응형 확인: 1920×1080, 1440×900, 390×844, 375×667, 320×568
- 가로 오버플로, 콘솔 오류, 실패한 정적 자산 요청 없음

검증용 화면은 [`docs/images/landing-page.jpg`](docs/images/landing-page.jpg)에 보관합니다.

---

## 문서

| 파일 | 성격 |
|---|---|
| [`MVP제안서.md`](MVP제안서.md) | 심사·발표용 문제·솔루션·공공가치 요약 |
| [`기술명세서.md`](기술명세서.md) | 아키텍처·데이터·AI·보안·평가 설계도 |
| [`spec.md`](spec.md) | 검증 가능한 Acceptance Criteria |
| [`plan.md`](plan.md) · [`tasks.md`](tasks.md) | 구현 계획과 태스크 DAG |
| [`app/README.md`](app/README.md) | 실행 모드와 LLM 라우팅 상세 |
| [`brand-spec.md`](brand-spec.md) | 랜딩페이지 시각 언어와 금지 규칙 |

---

## 로드맵

### P0 · 실데이터 연결

- [ ] 공공데이터 활용신청 승인 후 실제 응답 샘플 확보
- [ ] `clients.py` live-mode 구현과 KRC 호스트 allowlist 적용
- [ ] 오퍼레이션명·조회 파라미터·필드 타입 검증
- [ ] live 호출 실패 시 sample fallback과 상태 노출

### P1 · 정확도와 제품 완성도

- [x] 검색 중심 반응형 랜딩페이지와 브라우저 실제 렌더 검증
- [ ] 시군구 규칙 파싱 강화
- [ ] 지구 위치 지도와 인근 시설 표시
- [ ] 파싱 평가셋 30개에서 100개로 확대
- [ ] 규칙 파서와 LLM 파서 baseline 비교

### P2 · 운영 신뢰성

- [ ] GitHub Actions에 pytest·정적 검사 품질 게이트 추가
- [ ] API 성공률·응답시간·fallback 관측 화면
- [ ] LLM 라우팅 기준을 실측 비용과 정확도로 조정
- [ ] 공공데이터·생성 이미지·모델 자산대장 관리

### P3 · 확장

- [ ] 로컬 소형 모델 기반 개인정보 외부전송 0 모드
- [ ] KRC 지역개발사업·저수지 데이터 모듈 추가
- [ ] 귀농 지원정책·자금 정보 연동
- [ ] 발표용 데모 영상과 국민투표용 콘텐츠 제작

### 배포

- [ ] 프론트 정적 호스팅과 FastAPI 백엔드 배포 구성
- [ ] 실제 외부 배포는 운영 환경과 데이터 이용조건 검토 후 별도 승인

---

## 참조 시스템

- **AITHOR-Agent-Framework**: 파이프라인, verifier/evidence, guard, routing 패턴
- **minicpm5-poc**: 로컬 자연어 → JSON 파서 후보
- **AI-research-SKILLs**: 구조화 출력, LangGraph, guardrail, prompt 평가 패턴

> 현재 서비스는 sample-mode MVP입니다. 분양·계약·투자 결정을 확정하지 않으며, 최종 분양상태와 계약조건은 반드시 공식 기관에서 다시 확인해야 합니다.
