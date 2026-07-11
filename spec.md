# 전원마을 파인더 — SPEC (기능 명세 + Acceptance Criteria)

> 출처: `기술명세서.md` + `MVP제안서.md`. 본 문서는 **검증 가능한 AC**로 요구사항을 고정한다.

## S1. 목표
자연어 조건 → KRC 공공데이터 기반 "분양 가능한 전원마을 Top N" + 지역 가뭄 참고 패널 + 환각 방지 근거 리포트를 제공하는 **키 없이 실행 가능한(sample-mode) 웹 서비스**.

## S2. 범위
- 백엔드: FastAPI, 엔드포인트 3종, 결정론적 파이프라인.
- 데이터: KRC API 3종 클라이언트 + **샘플 캐시 fallback**(활용신청 전 키 없이 동작).
- AI: 자연어 파싱은 **결정론적 규칙 엔진**(MVP 코어) + LLM 어댑터 인터페이스(선택).
- 프론트: 정적 3화면(빌드 스텝 없는 HTML/CSS/JS).
- 테스트: pytest 유닛 + 엔드포인트 + 평가 테스트셋.

## S3. Acceptance Criteria (검증 가능)

| ID | AC | 검증 방법 |
|----|----|----------|
| AC1 | `POST /api/search`에 자연어 질의 시 Top 3 지구 카드 JSON 반환 | pytest + curl |
| AC2 | 각 카드는 진행단계·분양율·계획세대수(확정 데이터)를 포함 | pytest 스키마 검증 |
| AC3 | 응답의 모든 수치가 근거(evidence: api+field)에 바인딩됨. 미바인딩 값은 출력 안 됨 | pytest evidence 검증 |
| AC4 | 저수율/가뭄단계는 마을 점수에 **미포함**, 지역 패널로만 표시 | pytest scoring 검증(물 필드 미참조) |
| AC5 | 자연어 파싱: 지역/예산/진행단계/선호 추출 정확 (30문항 테스트셋 ≥ 80%) | pytest eval |
| AC6 | 데이터 신뢰도 등급(A~D) 표시, 부족 데이터는 "확인 불가" + 점수 제외 | pytest |
| AC7 | Input Guard: 주민번호/전화 등 PII 입력 차단·마스킹, injection 패턴 차단 | pytest guard |
| AC8 | 외부 호출은 KRC 호스트 allowlist만 허용(SSRF 방어) | pytest guard |
| AC9 | 키 없이 sample-mode로 전체 플로우 동작(오프라인) | 서버 기동 + curl |
| AC10 | 모든 응답에 "참고정보·최종확인 필요" 고지 부착 | pytest |
| AC11 | 3화면 프론트가 백엔드와 연동되어 검색 결과 렌더 | 서버 기동 + 화면 확인 |
| AC12 | `pytest` 전체 통과, `uvicorn` 기동 성공, `/api/health` 200 | 실행 검증 |

## S4. 비목표
- 실 계약/분양 확정 판단, 저수지↔마을 수혜구역 정밀 매칭, 예측 모델, 실제 외부 배포(deploy-ready까지만).

## S5. 데이터 계약 (핵심)
`POST /api/search` 응답:
```json
{
  "query_parsed": {"region":{"sido":"충청남도"},"budget_max_krw":200000000,"sale_stage":["분양중"],"preferences":["조용함"],"confidence":0.9},
  "top": [{"gu_id":"...","gu_name":"...","sido":"...","sigungu":"...","eupmyeon":"...",
           "sale_stage":"분양중","sale_rate":60,"planned_households":120,
           "score":0.82,"confidence_grade":"A","reasons":["..."]}],
  "drought_panel": {"sigungu":"...","drought_stage":"주의","normal_ratio":58,"base_date":"2026-07-20","note":"논가뭄지도 연1회 갱신·참고용"},
  "evidence": [{"claim":"분양율 60%","api":"15104395","field":"분양율","value":60}],
  "disclaimer": "공공데이터 기반 참고정보이며 최종 계약·분양은 공식 기관 확인이 필요합니다."
}
```
