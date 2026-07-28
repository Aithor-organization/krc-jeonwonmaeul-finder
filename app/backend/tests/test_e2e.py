"""E2E 시나리오 — 사용자 여정 전체를 end-to-end로 검증.

랜딩 → health → 자연어 검색 → Top-3 + 근거 바인딩 → 상세 조회 → 가뭄 패널.
FastAPI TestClient로 실제 앱 스택(라우팅·orchestrator·guard·scoring·evidence) 통합 실행.
"""
from fastapi.testclient import TestClient

import config
from main import app

client = TestClient(app)


def test_e2e_full_user_journey():
    # 1) 랜딩 페이지 진입 (검색 우선 UI)
    landing = client.get("/")
    assert landing.status_code == 200
    assert 'id="search-form"' in landing.text

    # 2) 헬스체크 — 운영 모드 노출
    health = client.get("/api/health")
    assert health.status_code == 200
    hj = health.json()
    assert hj["status"] == "ok"
    assert hj["sample_mode"] is True          # 현재 sample-mode
    assert hj["llm_enabled"] is config.LLM_ENABLED

    # 3) 자연어 검색 → Top-3 + 근거
    search = client.post("/api/search",
                         json={"query": "충남 예산 2억 분양 진행 중인 조용한 마을"})
    assert search.status_code == 200
    data = search.json()
    assert 1 <= len(data["top"]) <= 3
    top = data["top"][0]

    # 3-a) 카드의 모든 노출 수치가 evidence에 바인딩 (환각 방지 계약)
    assert data["evidence"], "근거가 비어 있으면 안 됨"
    for ev in data["evidence"]:
        assert ev["api"] and ev["field"]      # 모든 근거는 API+필드 출처
    # 카드 수치 → 근거 존재 확인
    claims = " ".join(e["claim"] for e in data["evidence"])
    if top["sale_stage"] is not None:
        assert "진행단계" in claims
    assert "참고정보" in data["disclaimer"]

    # 4) 상세 조회 — 카드에서 gu_id로 상세 진입
    gu_id = top["gu_id"]
    if gu_id:
        detail = client.get(f"/api/village/{gu_id}")
        assert detail.status_code == 200
        dj = detail.json()
        assert dj.get("gu_id") == gu_id
        assert "disclaimer" in dj             # 상세에도 고지 포함

    # 5) 가뭄 패널 — 지역 참고정보 (점수와 분리)
    assert data["drought_panel"] is not None
    assert "drought_stage" in data["drought_panel"]


def test_e2e_village_detail_not_found():
    r = client.get("/api/village/존재하지않는ID_zzz")
    assert r.status_code == 200
    assert r.json().get("error") == "not_found"


def test_e2e_structured_query_path():
    # 프론트가 구조화 쿼리를 직접 보내는 경로 (자연어 파싱 우회)
    r = client.post("/api/search", json={
        "structured": {
            "region": {"sido": "충청남도", "sigungu": None},
            "sale_stage": ["분양중"],
            "confidence": 0.8,
            "raw": "충남 분양중",
        }
    })
    assert r.status_code == 200
    data = r.json()
    assert data["query_parsed"]["region"]["sido"] == "충청남도"


def test_e2e_pii_in_query_is_masked_not_leaked():
    # 검색어에 PII가 섞여도 응답 어디에도 원문이 새지 않아야 함
    r = client.post("/api/search",
                    json={"query": "충남 분양 중 연락처 010-1234-5678"})
    assert r.status_code == 200
    body = r.text
    assert "010-1234-5678" not in body
