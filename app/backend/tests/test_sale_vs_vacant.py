"""분양받는 것과 마을 빈집을 카드가 구분해야 한다.

사용자 질문: "여기 보면 빈집이 없는데 도대체 왜 추천하는 거야?"

전원마을 조성사업은 **새 택지를 조성해 주택을 분양하는 신규마을 조성**이다
(농림축산식품부 「Ⅳ-1. 신규마을조성(전원마을 등)」). 진행단계가
준비 → 기반조성공사 → 주택건축 → 건축완료후 입주로 흐르는 것도 그 증거다.

따라서:
  · 분양 대상  = 이 지구에 **새로 조성되는** 계획세대수 (31세대 등)
  · 마을 빈집  = **옆에 있는 기존 마을**에 방치된 집 수 (쇠퇴 지표)

🔴 카드는 "계획세대수 31세대"라고만 적고 그게 분양 대상이라는 말을 안 했고,
빈집은 그냥 "빈집"이라고 적었다. 그러니 빈집이 들어갈 집으로 읽혔다.
데이터는 맞았고 **라벨이 오해를 만들었다**.
"""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def app_js() -> str:
    return client.get("/app.js").text


def test_vacant_label_says_it_is_the_villages():
    """🔴 그냥 '빈집'이면 분양받을 집으로 읽힌다."""
    js = app_js()
    for label in ("마을 빈집 없음", "마을 빈집 미조사"):
        assert label in js, label
    assert '"마을 빈집 " + esc(formatNumber(card.vacant_houses' in js


def test_bare_vacant_label_is_gone():
    """옛 라벨이 남아 있으면 같은 오해가 다시 난다."""
    import re
    js = re.sub(r"/\*.*?\*/", "", app_js(), flags=re.S)
    js = re.sub(r"^\s*//.*$", "", js, flags=re.M)
    assert '"빈집 없음"' not in js
    assert '"빈집 미조사"' not in js


def test_planned_households_is_labelled_as_the_thing_you_buy():
    """"계획세대수 31세대"만 적으면 그게 분양 대상인지 알 수 없다."""
    js = app_js()
    assert "METRIC_HINT" in js
    assert "이 지구에 새로 조성 — 분양 대상" in js
    # 값이 있을 때도 한 줄이 붙는지 (전에는 값이 없을 때만 붙었다)
    assert "unknown ? (reasonOverride || UNKNOWN_REASON[key]) : (METRIC_HINT[key]" in js


def test_village_note_denies_the_vacant_houses_are_for_sale():
    """마을 현황 줄이 '무엇의 값인가'만 말하고 '분양 대상인가'를 안 말했다."""
    js = app_js()
    assert "분양 대상이 아니며" in js
    assert "실제로 분양받는 것은 위의 계획세대수입니다" in js
    assert "옆에 있는 기존 마을" in js


def test_evidence_page_separates_the_two():
    page = client.get("/data-evidence.html").text
    assert "분양받는 것은 &lsquo;계획세대수&rsquo;이고" in page
    assert "신규마을 조성" in page
    assert "마을 빈집 <small>(분양 대상 아님)</small>" in page


def test_vacant_is_not_scored():
    """빈집은 표시만 하고 점수에 넣지 않는다 — 근거 페이지 라벨과 코드가 같아야 한다."""
    import scoring
    assert "빈집적음" not in scoring.SCORABLE_PREFS
    page = client.get("/data-evidence.html").text
    assert "<span class=\"pill caution\">표시만</span>" in page
