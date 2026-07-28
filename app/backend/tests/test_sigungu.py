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


# --- LLM이 넘긴 시군구도 같은 가드를 통과해야 한다 (2026-07-28) ---
def test_llm_sigungu_is_validated_against_budget_guard(monkeypatch):
    """LLM은 "충남 예산 2억"의 '예산'을 시군구와 금액 양쪽으로 읽는다 (실측).

    그대로 두면 예산군 1건으로 좁혀져 0건이 나온다 — 규칙 파서가 가진
    충돌 가드를 LLM 답에도 똑같이 적용해야 한다.
    """
    import config
    import intent
    import llm_intent
    from models import ParsedQuery, Region
    from orchestrator import Orchestrator

    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(
        llm_intent, "parse",
        lambda q, api_key=None: (
            ParsedQuery(region=Region(sido="충청남도", sigungu="예산"),
                        budget_max_krw=200_000_000, sale_stage=["분양중"],
                        confidence=0.9, raw=q),
            {"model": "gpt-x", "tier": "medium", "fallback": False}))

    r = Orchestrator().search(query="충남 예산 2억 분양 중")
    assert r.query_parsed.region.sigungu is None, "금액과 겹치는 이름을 지역으로 쓰면 안 된다"
    assert r.query_parsed.budget_max_krw == 200_000_000
    assert any("지역 조건으로 쓰지" in n for n in r.notes), "무시한 사실을 알려야 한다"


def test_llm_sigungu_shorthand_is_normalized(monkeypatch):
    """'곡성' → '곡성군'처럼 데이터에 있는 정식 이름으로 정규화한다."""
    import config
    import llm_intent
    from models import ParsedQuery, Region
    from orchestrator import Orchestrator

    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(
        llm_intent, "parse",
        lambda q, api_key=None: (
            ParsedQuery(region=Region(sido="전라남도", sigungu="곡성"),
                        confidence=0.9, raw=q),
            {"model": "gpt-x", "tier": "simple", "fallback": False}))
    r = Orchestrator().search(query="전남 곡성 마을")
    assert r.query_parsed.region.sigungu == "곡성군"
