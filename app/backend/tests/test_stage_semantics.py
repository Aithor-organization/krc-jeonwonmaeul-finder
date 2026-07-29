"""'분양중'은 "지금 들어갈 수 있다"가 아니다.

사용자 질문: "지금 들어갈 수 있는 곳인지 확인은 가능해?"

확인해 보니 우리 화면이 그렇다고 말하고 있었다 —
  · 히어로 제목: "좋아 보이는 곳 말고, **지금 들어갈 수 있는 곳**."
  · 점수 설명: "**지금 들어갈 수 있는지**가 가장 무겁습니다"

그런데 1.0점을 주는 `분양중`은 원천에서 **주택건축 단계**, 즉 집을 짓고
있는 중이다. 들어갈 수 없다. 반대로 건물이 완성된 `건축완료후 입주단계`는
이미 입주가 끝나 자리가 없어 0.1점이다.

우리가 재는 것은 "지금 **분양 절차가 진행 중인가**"이지 "입주 가능한가"가
아니다. 게다가 원천 9개 필드에 **갱신일·기준일이 하나도 없어** "지금"이라는
말 자체를 보증할 수 없다.
"""
import krc_mapping as km
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_source_stage_label_is_preserved():
    """원문을 버리면 '분양중'이 공사 중이라는 사실을 복원할 수 없다."""
    m = km.map_sale_item({"progrsStep": "주택건축 단계", "zoneName": "X",
                          "sidoNm": "충청남도", "sggNm": "예산군"})
    assert m["진행단계"] == "분양중"
    assert m["진행단계_원문"] == "주택건축 단계"


def test_all_five_source_labels_round_trip():
    """원천 5종이 전부 원문을 남기는지 (하나라도 빠지면 그 카드만 조용히 침묵)."""
    for src in ("준비단계", "기반조성공사단계", "주택건축 준비단계",
                "주택건축 단계", "건축완료후 입주단계"):
        m = km.map_sale_item({"progrsStep": src})
        assert m["진행단계_원문"] == src, src


def test_card_shows_the_source_label_beside_ours():
    js = client.get("/app.js").text
    assert "sale_stage_source" in js
    assert "badge-source" in js
    css = client.get("/results.css").text
    assert ".badge-source" in css


def test_response_carries_the_source_label():
    res = client.post("/api/search", json={"query": "충청남도 전원마을"}).json()
    assert res["top"], "결과가 없으면 확인할 수 없다"
    for c in res["top"]:
        if c["sale_stage"]:
            assert c["sale_stage_source"], c["gu_name"]


# ── 화면이 과장하지 않는가 ──

def test_headline_does_not_promise_move_in():
    """🔴 "지금 들어갈 수 있는 곳"은 이 데이터로 뒷받침되지 않는다.

    분양중(공사 중)도, 분양완료(자리 없음)도 지금 들어가 살 수 있는 곳이 아니다.
    """
    home = client.get("/").text
    assert "지금 들어갈 수 있는 곳" not in home
    assert "지금 분양 중인 곳" in home


def test_score_explanation_separates_sale_from_move_in():
    page = client.get("/how-it-works.html").text
    assert "지금 들어갈 수 있는지가 가장 무겁습니다" not in page
    assert "분양 절차가 진행 중인지" in page
    assert "입주 가능 여부가 아닙니다" in page


def test_evidence_page_publishes_the_stage_mapping():
    """원천 라벨 → 우리 라벨 대응이 공개돼야 '분양중'을 오해하지 않는다."""
    page = client.get("/data-evidence.html").text
    for label in ("주택건축 단계", "건축완료후 입주단계", "기반조성공사단계", "주택건축 준비단계"):
        assert label in page, label
    assert "집을 짓고 있는 중" in page


def test_evidence_page_discloses_missing_base_date():
    """'지금'을 보증할 기준일이 원천에 없다 — 이걸 안 밝히면 신선도를 파는 셈이다.

    실측: 분양정보 API 9개 필드에 날짜/갱신일 필드가 하나도 없다.
    """
    page = client.get("/data-evidence.html").text
    assert "기준일이 원천에 없습니다" in page
    assert "갱신일" in page and "언제 갱신된 것인지는 저희도 모릅니다" in page
