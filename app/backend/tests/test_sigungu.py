"""시군구 인식 — 데이터 기반 매칭 + 예산 오탐 가드."""
from fastapi.testclient import TestClient

import intent
from main import app
from orchestrator import Orchestrator

CANDIDATES = ["곡성군", "순천시", "예산군", "홍천군", "원주시", "고성군"]


# --- 순수 매칭 함수 ---
def test_full_name_match():
    assert intent.match_sigungu("전남 곡성군 분양 중", CANDIDATES) == "곡성군"
    assert intent.match_sigungu("순천시 마을", CANDIDATES) == "순천시"


def test_stem_match_without_suffix():
    """사용자는 보통 접미사를 생략한다 ('곡성' → 곡성군)."""
    assert intent.match_sigungu("전남 곡성 분양 중인 마을", CANDIDATES) == "곡성군"
    assert intent.match_sigungu("홍천 전원마을", CANDIDATES) == "홍천군"


def test_budget_collision_guarded():
    """'예산 2억'의 예산은 지역이 아니라 금액 — 오탐하면 조건이 둔갑한다."""
    assert intent.match_sigungu("충남 예산 2억 분양 중", CANDIDATES) is None
    assert intent.match_sigungu("예산 3000만원", CANDIDATES) is None
    # 전체명이면 지역이 명확하므로 숫자가 뒤따라도 매칭
    assert intent.match_sigungu("예산군 2억", CANDIDATES) == "예산군"


def test_no_match_cases():
    assert intent.match_sigungu("전남 분양 중", CANDIDATES) is None
    assert intent.match_sigungu("", CANDIDATES) is None
    assert intent.match_sigungu(None, CANDIDATES) is None
    assert intent.match_sigungu("곡성군", []) is None          # 후보 없으면 매칭 없음
    assert intent.match_sigungu("없는지역시", CANDIDATES) is None


def test_only_known_names_returned():
    """데이터에 없는 지역은 절대 만들어내지 않는다."""
    for q in ["서울 강남구 분양", "부산 해운대구"]:
        assert intent.match_sigungu(q, CANDIDATES) is None


# --- 클라이언트/오케스트레이터 통합 (sample-mode) ---
def test_available_sigungu_from_data():
    sgg = Orchestrator().client.available_sigungu()
    assert sgg == sorted(set(sgg))          # 정렬·중복 제거
    assert all(isinstance(s, str) and s for s in sgg)


def test_orchestrator_filters_by_sigungu():
    orch = Orchestrator()
    sgg_list = orch.client.available_sigungu()
    assert sgg_list, "샘플 데이터에 시군구가 있어야 함"
    target = sgg_list[0]

    resp = orch.search(query=f"{target} 마을")
    assert resp.query_parsed.region.sigungu == target
    assert all(c.sigungu == target for c in resp.top)


def test_sigungu_alone_is_a_recognized_condition():
    """시군구만 입력해도 '조건 미인식'으로 빠지지 않는다."""
    orch = Orchestrator()
    target = orch.client.available_sigungu()[0]
    resp = orch.search(query=target)
    assert not any("인식하지 못" in w for w in resp.warnings)


def test_budget_query_still_works_via_api():
    """'충남 예산 2억' 회귀 — 예산군으로 좁혀지지 않고 시도 검색이 유지된다."""
    c = TestClient(app)
    d = c.post("/api/search", json={"query": "충남 예산 2억 분양 진행 중"}).json()
    assert d["query_parsed"]["region"]["sido"] == "충청남도"
    assert d["query_parsed"]["region"]["sigungu"] is None
    assert len(d["top"]) >= 1
