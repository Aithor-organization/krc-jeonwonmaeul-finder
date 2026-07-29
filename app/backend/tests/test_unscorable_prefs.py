"""판정할 데이터가 없는 선호는 점수에서 빼고, 뺐다는 사실을 알린다.

이전에는 분모에 넣었다. 대조할 필드가 없어 100% 미부합했으므로 조건을 적을수록
점수가 내려갔다 — 실측으로 "강원 스마트팜 마을"(0.65)이 "강원 마을"(0.75)보다
낮았다. 반영된 것도 무시된 것도 아닌 상태가 가장 나쁘다.
"""
from fastapi.testclient import TestClient

import scoring
from main import app

client = TestClient(app)


def score_of(query: str) -> float:
    got = client.post("/api/search", json={"query": query}).json()
    assert got["top"], query
    return got["top"][0]["score"]


def pref_term(query: str) -> dict:
    got = client.post("/api/search", json={"query": query}).json()
    terms = got["trace"]["scores"][0]["terms"]
    return next(t for t in terms if t["label"] == "선호매칭")


def test_unscorable_pref_does_not_lower_the_score():
    """🔴 핵심 회귀 — 판정 못 하는 조건을 적었다고 감점되면 안 된다."""
    plain = score_of("충남 분양 중인 마을")
    with_pref = score_of("충남 분양 중인 스마트팜 마을")
    assert with_pref == plain, f"스마트팜을 적자 {plain} → {with_pref}로 바뀌었다"


def test_unscorable_pref_keeps_neutral_term():
    term = pref_term("충남 분양 중인 스마트팜 마을")
    assert term["value"] == 0.5, "판정 불가 조건만 있으면 중립값이어야 한다"
    assert "판정 가능한 선호 조건 없음" in term["basis"]


def test_scorable_pref_still_works():
    """조용함은 인구로 대조할 수 있으므로 점수에 반영돼야 한다."""
    plain = score_of("충남 분양 중인 마을")
    quiet = score_of("충남 분양 중인 조용한 마을")
    assert quiet != plain, "조용함이 점수에 반영되지 않는다"
    assert pref_term("충남 분양 중인 조용한 마을")["value"] in (0.0, 1.0)


def test_unscorable_pref_is_disclosed():
    """조용히 빼면 사용자는 반영됐다고 믿는다."""
    got = client.post("/api/search", json={"query": "충남 스마트팜 교통 좋은 마을"}).json()
    joined = " ".join(got["warnings"])
    assert "점수에 반영하지 못했습니다" in joined
    assert "스마트팜" in joined and "교통편의" in joined
    assert "공공데이터에 없습니다" in joined, "이유를 함께 밝혀야 한다"


def test_mixed_prefs_score_only_the_scorable_one():
    """판정 가능한 것만 분모에 들어간다 (조용함 1개 → 1/1)."""
    term = pref_term("충남 분양 중인 조용하고 스마트팜 있는 마을")
    assert "선호 1개 중" in term["basis"], term["basis"]


def test_two_pref_sets_are_disjoint_and_cover_the_parser():
    """파서가 만드는 라벨은 전부 둘 중 하나로 분류돼 있어야 한다.

    새 선호를 추가하고 어느 쪽에도 넣지 않으면, 그 조건은 조용히
    감점 요인으로 돌아온다 (이번에 고친 버그의 재발 경로).
    """
    from intent import _PREF_KEYWORDS
    labels = {label for _, label in _PREF_KEYWORDS}
    assert not (scoring.SCORABLE_PREFS & set(scoring.UNSCORABLE_PREFS))
    uncovered = labels - scoring.SCORABLE_PREFS - set(scoring.UNSCORABLE_PREFS)
    assert not uncovered, f"어느 쪽에도 분류되지 않은 선호: {uncovered}"
