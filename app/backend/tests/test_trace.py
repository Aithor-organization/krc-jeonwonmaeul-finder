"""계산 내역(trace) — 표시값이 실제 결과와 어긋나지 않음을 고정한다.

이 패널의 존재 이유가 "할루시네이션이 아님을 보이는 것"이므로,
패널 자체가 틀린 숫자를 말하면 목적이 정반대로 뒤집힌다.
"""
from fastapi.testclient import TestClient

import scoring
from main import app
from orchestrator import Orchestrator

client = TestClient(app)


def _search(q="충남 분양 중인 마을"):
    return Orchestrator().search(query=q)


# --- 산식 전개가 실제 점수와 일치 ---
def test_terms_sum_to_card_score():
    r = _search()
    assert r.trace and r.trace.scores
    for cs in r.trace.scores:
        card = next(c for c in r.top if c.gu_id == cs.gu_id)
        assert cs.total == card.score, "trace 총점이 카드 점수와 다르다"
        assert abs(sum(t.contribution for t in cs.terms) - card.score) < 0.002, \
            f"{cs.gu_name}: 항 합계 != 점수"


def test_breakdown_shares_source_with_score():
    """score_breakdown과 score_card가 같은 _terms를 쓰는지 — 드리프트 차단."""
    sale = {"진행단계": "분양중", "분양율": 40, "계획세대수": 50}
    parsed = _search().query_parsed
    score, _, _ = scoring.score_card(parsed, sale, None)
    terms = scoring.score_breakdown(parsed, sale, None)
    assert abs(sum(t["weight"] * t["value"] for t in terms) - score) < 0.002


def test_weights_match_declared_formula():
    terms = scoring.score_breakdown(_search().query_parsed,
                                    {"진행단계": "분양중", "분양율": 0}, None)
    assert [t["weight"] for t in terms] == [0.5, 0.3, 0.2]
    for t in terms:
        assert str(t["weight"]) in scoring.FORMULA


# --- funnel이 실제 건수와 일치 ---
def test_funnel_starts_from_total_and_ends_at_displayed():
    r = _search()
    f = r.trace.funnel
    assert f[0].label.startswith("전국")
    assert f[0].count >= f[-1].count
    assert f[-1].count == len(r.top), "마지막 단계 건수가 실제 표시 건수와 다르다"


def test_funnel_dropped_matches_step_delta():
    """탈락 수 = 직전 단계 − 현재 단계. 임의로 적으면 신뢰가 깨진다."""
    f = _search().trace.funnel
    for prev, cur in zip(f, f[1:]):
        assert cur.dropped == prev.count - cur.count, f"{cur.label}: 탈락 수 불일치"


def test_funnel_reflects_narrower_query():
    wide = _search("충남")
    narrow = _search("충남 분양 중")
    assert len(narrow.trace.funnel) > len(wide.trace.funnel), "조건이 늘면 단계도 늘어야 함"


# --- 파서 주체를 정직하게 표기 ---
def test_parser_label_is_rule_parser_without_key():
    r = _search()
    assert "규칙" in r.trace.parser
    assert r.trace.deterministic is True


def test_llm_scope_excludes_ranking():
    r = _search()
    assert "순위" in r.trace.llm_scope


def test_parser_label_stays_rule_when_llm_falls_back(monkeypatch):
    """폴백이면 실제로 해석한 건 규칙 파서다 — 모델명을 적으면 거짓이 된다."""
    import config
    import intent
    import llm_intent
    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(llm_intent, "parse",
                        lambda q, api_key=None: (intent.parse(q),
                                                 {"model": "gpt-x", "tier": "simple",
                                                  "fallback": True, "error": "boom"}))
    r = _search()
    assert "규칙" in r.trace.parser
    assert "gpt-x" not in r.trace.parser


def test_parser_label_names_model_on_success(monkeypatch):
    import config
    import intent
    import llm_intent
    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(llm_intent, "parse",
                        lambda q, api_key=None: (intent.parse(q),
                                                 {"model": "gpt-x", "tier": "simple",
                                                  "fallback": False}))
    assert "gpt-x" in _search().trace.parser


# --- API 계약 ---
def test_api_returns_trace():
    r = client.post("/api/search", json={"query": "충남 분양 중"})
    assert r.status_code == 200
    t = r.json()["trace"]
    assert t["funnel"] and t["scores"]
    assert t["deterministic"] is True


def test_same_query_gives_same_trace():
    """재현 가능성이 이 기능의 핵심 주장이다."""
    a = client.post("/api/search", json={"query": "충남 분양 중"}).json()["trace"]
    b = client.post("/api/search", json={"query": "충남 분양 중"}).json()["trace"]
    assert a == b


def test_empty_result_has_no_trace():
    """계산이 일어나지 않았으면 계산 내역도 없다 — 빈 패널을 그리지 않는다."""
    r = client.post("/api/search", json={"query": "asdfqwer"}).json()
    assert r["top"] == []
    assert r["trace"] is None
