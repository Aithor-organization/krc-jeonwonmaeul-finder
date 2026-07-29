"""분양율을 얼마나 믿을 수 있는지 네 상태로 가른다.

사용자 지적: "이미 다 들어갔으면 100%일 텐데, 확실한 곳은 확실하게 보여주고
그렇지 않은 곳은 데이터가 없다고 하는 게 맞지 않나?"

절반은 맞고 절반은 위험하다.
  · 맞는 부분 — 화면이 '수치 있음 / 확인 불가' 둘로만 갈라서, **우리가 아는
    17건이 정말 모르는 124건과 같은 칸**에 들어갔다. 분양완료 지구는 수치가
    없어도 남은 자리가 없다는 걸 알고 점수(가용성 0)에 이미 쓰고 있었는데
    화면에서만 감췄다.
  · 위험한 부분 — 그렇다고 100%라고 **숫자로 적으면** 없는 수치를 만드는 것이다.
    같은 100%가 분양예정 단계에도 12건 있어(집을 짓기 전인데) 100이라는 값의
    의미 자체가 확실하지 않다.

결론: 판정("남은 자리 없음")은 표시하고, 수치는 만들지 않는다.
"""
import krc_mapping as km
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def status(rate, over=None, stage=None):
    return km.rate_status(rate, over, stage)


# ── 네 상태가 실제로 갈리는가 ──

def test_four_states_are_distinct():
    assert status(60.0, stage="분양중") == "확정"
    assert status(None, stage="분양완료") == "추정"
    assert status(None, over=150.0, stage="분양예정") == "보류"
    assert status(None, stage="분양중") == "미상"


def test_inferred_only_applies_to_completed_stage():
    """분양중·분양예정의 미입력은 정말 모르는 것이다 — 추정으로 올리면 안 된다.

    실측: 분양중 60건·분양예정 64건이 미입력. 이걸 '남은 자리 없음'으로
    판정할 근거가 없다.
    """
    assert status(None, stage="분양중") == "미상"
    assert status(None, stage="분양예정") == "미상"
    assert status(None, stage=None) == "미상"


def test_explicit_value_beats_stage_inference():
    """수치가 있으면 단계 추정을 쓰지 않는다."""
    assert status(100.0, stage="분양완료") == "확정"
    assert status(30.0, stage="분양완료") == "확정"


# ── 단계와 수치가 어긋나는 조합 ──

def test_anomaly_flags_sold_out_before_construction():
    """분양예정(집 짓기 전)인데 100% — 전국 12건. 지우지도 고치지도 않고 알린다."""
    note = km.rate_anomaly(100.0, "분양예정")
    assert note and "분양예정" in note and "100%" in note


def test_anomaly_is_silent_when_consistent():
    """정상 조합에까지 경고를 붙이면 경고가 의미를 잃는다."""
    assert km.rate_anomaly(100.0, "분양완료") is None
    assert km.rate_anomaly(60.0, "분양중") is None
    assert km.rate_anomaly(None, "분양예정") is None


# ── 카드까지 도달하는가 ──

def test_status_reaches_the_card():
    res = client.post("/api/search", json={"query": "충청남도 전원마을"}).json()
    assert res["top"], "결과가 없으면 확인할 수 없다"
    for c in res["top"]:
        assert c["sale_rate_status"] in {"확정", "추정", "보류", "미상"}, c["sale_rate_status"]


def test_status_is_bound_to_evidence():
    """추정은 수치가 아니라 판단이다 — 무엇으로부터 추정했는지 근거에 남아야 한다."""
    import evidence as evidence_mod
    from models import VillageCard
    card = VillageCard(gu_id="X", gu_name="완료지구", sido="충청남도", sigungu="예산군",
                       sale_stage="분양완료", sale_rate_status="추정")
    ev = evidence_mod.build_evidence(card)
    hit = next(e for e in ev if "분양율 상태" in e.claim)
    assert "progrsStep" in hit.field, "무엇으로부터 추정했는지가 field에 있어야 한다"
    assert evidence_mod.is_fully_bound(card, ev)


def test_inferred_card_says_no_room_not_a_number():
    """🔴 추정 카드는 '남은 자리 없음'이라고 쓰고 100%라고 쓰지 않는다."""
    js = client.get("/app.js").text
    assert '"남은 자리 없음"' in js
    assert "100%" not in js.split("function metricHtml")[1].split("function metricsHtml")[0]


def test_card_separates_inferred_from_missing():
    """추정과 미상이 같은 회색으로 보이면 가른 의미가 없다."""
    js = client.get("/app.js").text
    assert "RATE_STATUS" in js
    for label in ("원천 기록", "단계로 추정", "기록 없음"):
        assert label in js, label
    css = client.get("/results.css").text
    assert ".rate-tag.is-inferred" in css and ".rate-tag.is-confirmed" in css
    assert ".metric.is-unknown.is-inferred .value" in css, "추정 값이 미상과 같은 색이면 안 된다"


def test_inferred_sorts_ahead_of_missing():
    """추정은 내용이 있으므로 미상보다 앞에 온다."""
    fn = client.get("/app.js").text.split("function metricsHtml")[1].split("\n/**")[0]
    assert "m.value != null ? 0" in fn and '"추정" ? 1 : 2' in fn


def test_anomaly_notice_renders():
    js = client.get("/app.js").text
    assert "sale_rate_anomaly" in js and "rate-anomaly" in js
    assert "분양처 확인이 필요합니다" in js


def test_sample_mode_zero_is_not_shown_as_zero_percent():
    """샘플은 map_sales를 거치지 않는다 — 0을 그대로 두면 라이브와 달라진다.

    라이브는 map_sale_rate(0) → None("확인 불가")인데 샘플만 "0%"로 보이면,
    키 없이 여는 사람은 있지도 않은 수치를 본다.
    """
    import json
    from pathlib import Path
    rows = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "samples" / "jeonwon_sale.json")
        .read_text(encoding="utf-8"))
    assert 0 not in [r.get("분양율") for r in rows]
    for r in rows:
        assert r["분양율_상태"] == km.rate_status(
            r.get("분양율"), r.get("분양율_범위초과"), r.get("진행단계")), r["지구명"]


def test_evidence_page_publishes_the_cross_tab():
    """왜 이렇게 갈랐는지의 근거(교차표)가 공개돼야 한다."""
    page = client.get("/data-evidence.html").text
    assert "단계로 추정" in page
    assert "분양예정 단계에도 12곳" in page, "100%의 의미가 불확실한 근거를 밝혀야 한다"
    assert "100%라고 적지는 않습니다" in page
