"""분양율이 '무엇의' 값인지 화면이 밝히는가.

사용자 질문: "여기서 말하는 분양율이 한 곳의 분양율이야, 그 지역의 분양율이야?"

답은 **지구 한 곳**이다. 원천 레코드 하나가 지구 하나이고, 같은 시군구 안에서
값이 갈린다 — 강원 원주시에 100%(지정새싹)와 0%(서곡)가 함께 있다.
지역 단위였다면 같아야 한다.

질문이 나온 이유는 카드가 두 단위를 한 칸에 쌓아 뒀기 때문이다:

    분양율                              ← 이 지구 하나
    확인 불가
    원천 미입력 (167건 중 141건이 0)      ← 전국 전체

위아래 단위가 다른데 구분이 없었다. 여기서 그 구분을 고정한다.
"""
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
SALES = Path(__file__).resolve().parents[1] / "data" / "samples" / "jeonwon_sale.json"


def app_js() -> str:
    return client.get("/app.js").text


def app_js_code() -> str:
    """주석을 뺀 app.js.

    🔴 주석을 남겨 두면 안 된다 — 이 파일의 주석은 옛 문구를 **인용해서**
    무엇이 문제였는지 설명한다. 그대로 매칭하면 "옛 문구가 사라졌는지"
    검사가 자기가 읽는 설명문에 걸려 영원히 실패한다 (실제로 그랬다).
    """
    js = app_js()
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"^\s*//.*$", "", js, flags=re.M)


# ── 원천이 정말 지구 단위인가 (샘플로 고정, 라이브 실측과 같은 성질) ──

def test_source_records_are_per_district_not_per_region():
    """같은 시군구에 값이 다른 지구가 있으면 지역 단위일 수 없다.

    라이브 167건 실측: 한 시군구 안에서 분양율이 갈리는 곳이 9곳
    (원주시 100/0, 괴산군 100/0, 홍성군 100/0 …).
    """
    rows = json.loads(SALES.read_text(encoding="utf-8"))
    by_region: dict[tuple, set] = {}
    for r in rows:
        key = (r.get("시도명"), r.get("시군구"))
        by_region.setdefault(key, set()).add(r.get("분양율"))

    split = {k: v for k, v in by_region.items() if len(v) > 1}
    assert split, (
        "샘플에 같은 시군구·다른 분양율 조합이 없다 — 지구 단위임을 보이는 "
        "사례가 사라지면 이 성질을 회귀로 잡을 수 없다"
    )
    # 지구명도 서로 달라야 한다 (같은 지구의 중복 등록이 아니라 별개 지구)
    for (sido, sgg) in split:
        names = {r["지구명"] for r in rows
                 if r.get("시도명") == sido and r.get("시군구") == sgg}
        assert len(names) > 1, (sido, sgg, names)


def test_out_of_range_rate_is_held_back_not_shown_as_a_number():
    """100을 넘는 값은 수치로 표시하지 않는다 (기존 정책 유지).

    라이브 실측: 전남 구례 '남도'가 150%(계획 20세대).
    """
    import krc_mapping
    assert krc_mapping.map_sale_rate(150) is None
    assert krc_mapping.map_sale_rate(100) == 100.0
    assert krc_mapping.map_sale_rate(0) is None


def test_out_of_range_reason_differs_from_missing():
    """🔴 '없음'과 '범위를 벗어남'은 이유가 다르다 — 다르게 말해야 한다.

    남도는 원천에 150%가 적혀 있다. 화면이 "원천에 값이 없음"이라고 하면
    그건 사실이 아니다. 같은 '확인 불가'라도 사유는 구분한다.
    """
    import krc_mapping
    assert krc_mapping.out_of_range_rate(150) == 150.0
    assert krc_mapping.out_of_range_rate(80) is None
    assert krc_mapping.out_of_range_rate(0) is None

    mapped = krc_mapping.map_sale_item(
        {"zoneName": "남도", "bndeLttotHscntPer": 150, "planHscnt": 20,
         "progrsStep": "준비단계", "sidoNm": "전남광주통합특별시", "sggNm": "구례군"})
    assert mapped["분양율"] is None
    assert mapped["분양율_범위초과"] == 150.0

    code = app_js_code()
    assert "sale_rate_out_of_range" in code
    assert "100%를 넘어 표시를 보류했습니다" in code


def test_out_of_range_reaches_the_card():
    """매핑만 하고 카드에 안 실으면 화면은 여전히 '원천에 없음'이라고 말한다."""
    res = client.post("/api/search", json={"query": "충청남도 전원마을"}).json()
    assert res["top"], "결과가 없으면 확인할 수 없다"
    assert "sale_rate_out_of_range" in res["top"][0]


def test_score_clamps_but_display_does_not():
    """점수는 0~100으로 보정하되, 화면 표시는 원천 값을 유지한다.

    두 곳이 같은 규칙을 쓰면 안 된다 — 가용성은 (100−분양율)/100이라
    150%를 그대로 넣으면 음수가 되고, 표시는 원천이 진실이다.
    """
    import scoring
    from models import ParsedQuery
    sale = {"지구명": "남도", "진행단계": "준비단계", "분양율": 150.0, "계획세대수": 20}
    avail = next(t for t in scoring.score_breakdown(ParsedQuery(), sale, None)
                 if t["label"] == "가용성")
    assert avail["value"] == 0.0, "150%가 음수 가용성을 만들면 안 된다"


# ── 화면이 단위를 밝히는가 ──

def test_metric_shows_which_scope_it_belongs_to():
    """지표 칸에 '이 지구 기준'이 항상 보여야 한다.

    툴팁만으로는 안 읽힌다 — 이 카드에서 가장 자주 오해받는 지점이다.
    """
    js = app_js()
    assert "metric-scope" in js
    assert "이 지구 기준" in js
    assert "시군구·지역 전체 값이 아닙니다" in js, "정의가 툴팁에라도 있어야 한다"

    css = client.get("/results.css").text
    assert ".metric-scope" in css, "클래스만 붙이고 스타일이 없으면 안 보인다"


def test_unknown_reason_separates_this_district_from_the_nationwide_count():
    """미입력 사유에서 '이 지구'와 '전국 167곳'이 구분돼야 한다.

    🔴 이 구분이 없어서 질문이 나왔다. 옛 문구는 "원천 미입력 (167건 중
    141건이 0)"으로, 지구 값 자리에 전국 통계만 덩그러니 있었다.
    """
    code = app_js_code()
    assert "이 지구 값이 원천에 없음" in code
    assert "전국 167곳 중 141곳이 같음" in code
    # 스코프 표시 없는 옛 문구가 되살아나면 실패 (주석의 인용은 제외)
    assert "원천 미입력 (167건 중 141건이 0)" not in code


def test_stage_based_reasons_also_name_the_district():
    """단계로 유추한 사유도 이 지구 얘기임을 밝힌다."""
    js = app_js()
    assert "이 지구는 수치 미입력이지만 분양완료" in js
    assert "이 지구는 분양 시작 전이라 기록 없음" in js


def test_evidence_page_defines_the_rate_scope():
    """근거 페이지가 정의의 출처여야 한다 — 카드는 요약만 한다."""
    page = client.get("/data-evidence.html").text
    assert "분양율은 지구 한 곳의 값입니다" in page
    assert "지역 전체 값이 아닙니다" in page
    assert "9곳" in page, "같은 시군구에서 값이 갈리는 사례 수를 근거로 제시해야 한다"
    assert "150%" in page, "100% 초과 사례를 밝혀야 한다"
    # 🔴 실제 동작과 어긋나는 문장이 있으면 안 된다. 초안에는 "150%를 그대로
    # 보여 줍니다"라고 썼는데, map_sale_rate가 100 초과를 이미 떨구고 있었다 —
    # 근거 페이지가 코드와 반대로 말하고 있었다.
    assert "그대로</strong> 보여 줍니다" not in page
    assert "표시하지 않고 보류" in page
