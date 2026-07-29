"""지역 드롭다운 목록 — 새 API 없이 검색 데이터에서 도출한다.

이 목록의 존재 이유는 "고를 수 있는 것 = 결과가 나오는 것"을 보장하는 것이다.
별도 행정구역 API에서 받아오면 데이터에 없는 지역이 목록에 섞이고, 고르면
0건이 나온다. 그래서 검색에 쓰는 바로 그 데이터에서 뽑는지 검사한다.
"""
from fastapi.testclient import TestClient

import krc_live
from clients import KrcDataClient
from main import app

client = TestClient(app)


def test_regions_endpoint_returns_tree():
    response = client.get("/api/regions")
    assert response.status_code == 200
    payload = response.json()
    assert payload["시도"], "시도 목록이 비면 드롭다운이 뜨지 않는다"
    assert payload["총건수"] > 0
    assert payload["기준"] in ("live", "sample")


def test_sido_counts_sum_to_total():
    """건수를 화면에 표시하므로 합이 맞아야 한다 — 안 맞으면 그 숫자가 거짓이다."""
    payload = client.get("/api/regions").json()
    assert sum(s["건수"] for s in payload["시도"]) == payload["총건수"]


def test_sigungu_counts_never_exceed_their_sido():
    payload = client.get("/api/regions").json()
    for sido in payload["시도"]:
        assert sum(g["건수"] for g in sido["시군구"]) <= sido["건수"], sido["이름"]


def test_every_listed_region_actually_returns_results():
    """🔴 목록에 있는데 검색하면 0건이면, 그 드롭다운은 사용자를 속인다."""
    payload = client.get("/api/regions").json()
    for sido in payload["시도"]:
        found = client.post("/api/search", json={"structured": {
            "region": {"sido": sido["이름"], "sigungu": None},
            "sale_stage": [], "preferences": [], "confidence": 1, "raw": sido["이름"],
        }}).json()
        assert found["top"], f"{sido['이름']}: 목록에 있는데 결과 0건"

        for gu in sido["시군구"]:
            got = client.post("/api/search", json={"structured": {
                "region": {"sido": sido["이름"], "sigungu": gu["이름"]},
                "sale_stage": [], "preferences": [], "confidence": 1, "raw": gu["이름"],
            }}).json()
            assert got["top"], f"{sido['이름']} {gu['이름']}: 목록에 있는데 결과 0건"


def test_listed_stages_return_results():
    payload = client.get("/api/regions").json()
    assert payload["진행단계"], "진행단계 목록이 비면 해당 드롭다운이 무의미하다"
    for stage in payload["진행단계"]:
        got = client.post("/api/search", json={"structured": {
            "region": {"sido": None, "sigungu": None},
            "sale_stage": [stage["이름"]], "preferences": [], "confidence": 1,
            "raw": stage["이름"],
        }}).json()
        assert got["top"], f"{stage['이름']}: 목록에 있는데 결과 0건"


def test_structured_search_skips_sentence_parsing():
    """드롭다운 선택을 문장으로 되돌려 파싱하면 추측이 끼어든다.

    실제로 '예산'이 시군구와 금액으로 동시에 읽혀 0건이 된 적이 있다.
    structured 경로는 그 단계를 건너뛰어야 한다.
    """
    got = client.post("/api/search", json={"structured": {
        "region": {"sido": "충청남도", "sigungu": None},
        "sale_stage": [], "preferences": [], "confidence": 1, "raw": "충청남도",
    }}).json()
    assert got["trace"]["parser"] == "구조화 입력 (문장 파싱 없음)"
    assert got["trace"]["deterministic"] is True
    assert got["query_parsed"]["region"]["sido"] == "충청남도"


def test_region_tree_does_not_call_upstream_again(monkeypatch):
    """목록은 이미 받아온 분양 데이터에서 뽑는다 — 새 공공데이터 호출이 있으면 안 된다."""
    calls = {"n": 0}

    def counting_fetch(key, **kw):
        calls["n"] += 1
        return []

    monkeypatch.setattr(krc_live, "fetch_sales", counting_fetch)
    c = KrcDataClient(sample_mode=True)      # 키 없음 = 상류 호출 자체가 없어야 함
    c.ensure_loaded()
    c.region_tree()
    c.region_tree()
    assert calls["n"] == 0, f"region_tree가 상류를 {calls['n']}회 호출했다"


def test_region_tree_survives_missing_fields():
    """시도명이 빈 레코드가 섞여도 목록이 죽지 않는다 (원천 데이터는 늘 깨끗하지 않다)."""
    c = KrcDataClient(sample_mode=True)
    c.ensure_loaded()
    c._sale = [{"시도명": "", "시군구": "", "진행단계": ""},
               {"시도명": "충청남도", "시군구": "예산군", "진행단계": "분양중"}]
    tree = c.region_tree()
    assert [s["이름"] for s in tree["시도"]] == ["충청남도"]
    assert tree["총건수"] == 2, "총건수는 실제 레코드 수 — 집계에서 빠진 것도 데이터다"
