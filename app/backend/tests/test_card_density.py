"""카드가 막다른 길이 되지 않게, 그리고 덤프가 되지 않게.

사용자 지적: "이것만 보는 거면 정보가 적다고 생각하지 않을까?"

카드를 실측해 보니 문제는 '적다'가 아니라 **카드마다 정반대**였다.
  · 자원 없는 110곳(87%) — 얇다
  · 자원 있는 17곳 — 항목 중앙값 11개(최대 15개·우동 2,228자).
    충주 앙성 카드는 높이 1,421px로 화면 하나를 넘었고 그 안에
    "논 보통답 : 17 사질답 : 57 미숙답 : 73" 같은 토양 통계가 들어 있었다.

그리고 공통으로 **다음 행동이 없었다** — 지도·시군구청 안내가 전부
`근거 확인` 모달 안에만 있어서 카드만 읽은 사람은 읽고 끝났다.
"정보가 적다"고 느끼는 지점은 필드 수가 아니라 여기라고 본다.
"""
import re

import orchestrator
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def app_js() -> str:
    return client.get("/app.js").text


def app_js_code() -> str:
    """주석을 뺀 app.js.

    🔴 이 파일의 주석은 "어떤 문구를 쓰면 안 되는지"를 그 문구를 인용해서
    설명한다. 주석을 남겨 두면 "그 문구가 사라졌는지" 검사가 자기가 읽는
    설명문에 걸린다 — 이 세션에서만 세 번 겪었다.
    """
    js = re.sub(r"/\*.*?\*/", "", app_js(), flags=re.S)
    return re.sub(r"^\s*//.*$", "", js, flags=re.M)


# ── 통계 덤프 판별 ──

SOIL = ("1. 기후 - 평균기온 : 중부 지방의 평균 기온 10℃ 2. 토양(흙토람 토양통계자료 "
        "영죽리 기준) 논 보통답 : 17 사질답 : 57 미숙답 : 73 습 답 : 1 합 계 : 148 "
        "밭 보통전 : 127 사질전 : 100 미숙전 : 0 중점전 : 0 합 계 : 227")
CROPS = "■ 농산물 : 감, 오이, 쑥, 매실, 포도, 도라지, 블루베리, 감자, 고구마, 밤, 콩, 고추"


def test_soil_table_is_detected_as_a_dump():
    assert orchestrator.is_statistic_dump(SOIL)


def test_crop_list_is_not_a_dump():
    """농산물 목록은 길어도 사람이 읽는 문장이다 — 접으면 안 된다."""
    assert not orchestrator.is_statistic_dump(CROPS)


def test_short_text_is_never_a_dump():
    """짧은 항목은 숫자가 많아도 접지 않는다 (예: '연평균기온 12.3℃')."""
    assert not orchestrator.is_statistic_dump("■ 연평균기온 : 12.3℃ 연강수량 1,967mm")


def test_dump_split_keeps_both_sides():
    """접는 것이지 지우는 것이 아니다 — 양쪽 다 남아야 한다."""
    main, detail = orchestrator._clean_resources({"자연": [SOIL, "■ 우산보"],
                                                  "생산·경제": [CROPS]})
    assert main["생산·경제"] == [CROPS]
    assert main["자연"] == ["■ 우산보"]
    assert detail["자연"] == [SOIL]


def test_dump_split_still_passes_the_output_guard():
    """나누는 과정에서 가드를 건너뛰면 여기가 유일한 구멍이 된다."""
    main, detail = orchestrator._clean_resources({"자연": ["연락처 010-1234-5678 로 문의"]})
    assert "010-1234-5678" not in str(main) + str(detail)


def test_no_resources_yields_two_nones():
    assert orchestrator._clean_resources(None) == (None, None)
    assert orchestrator._clean_resources({}) == (None, None)


# ── 화면 ──

def test_dump_is_folded_not_dropped():
    js = app_js()
    assert "res-detail" in js and "<details" in js
    # 🔴 라벨이 "통계 원문 N건"이면 거짓이다 — 접힌 것에는 개수 상한을 넘긴
    # 일반 항목도 섞인다(실측: 8건 중 6건이 일반). 중립적으로 세기만 한다.
    code = app_js_code()
    assert "자원 원문 " in code and "건 더 보기" in code
    assert "통계 원문 " not in code, "접힌 것을 전부 통계라고 부르면 안 된다"
    assert "펼치면 원문 그대로 나옵니다" in code, "감춘 게 아님을 밝혀야 한다"
    css = client.get("/results.css").text
    assert ".res-detail" in css


def test_card_offers_next_steps_without_opening_the_modal():
    """🔴 지도·시군구청이 모달 안에만 있으면 카드는 막다른 길이다."""
    js = app_js()
    fn = js.split("function cardActionsHtml")[1].split("\nfunction ")[0]
    assert "map.kakao.com" in fn, "지도 링크가 카드에 있어야 한다"
    assert "문의처 찾기" in fn
    assert "card.sigungu" in fn


def test_office_link_is_a_search_not_a_made_up_url():
    """지자체 도메인은 제각각이라 정확한 주소를 알 수 없다 —
    모르는 URL을 지어내느니 검색을 여는 편이 정직하다."""
    fn = app_js().split("function cardActionsHtml")[1].split("\nfunction ")[0]
    assert "google.com/search?q=" in fn
    # 시군구 이름으로 도메인을 조립하는 흔적이 있으면 그건 지어낸 주소다
    assert ".go.kr" not in fn


def test_card_actions_state_what_is_missing():
    """다음 행동 옆에 '여기서는 못 얻는 것'을 같이 적는다."""
    fn = app_js().split("function cardActionsHtml")[1].split("\nfunction ")[0]
    assert "분양가" in fn and "신청 일정" in fn


def test_stage_reason_is_not_repeated_under_the_badge():
    """배지에 '분양중'이 있는데 선정 이유에 '진행단계=분양중'이 또 나왔다.

    응답(reasons)은 그대로 두고 화면에서만 뺀다 — API 계약을 바꾸지 않는다.
    """
    js = app_js()
    assert '"진행단계=" + card.sale_stage' in js

    res = client.post("/api/search", json={"query": "충청남도 전원마을"}).json()
    card = res["top"][0]
    assert any(r.startswith("진행단계=") for r in card["reasons"]), \
        "응답에서는 사라지면 안 된다 (점수 근거)"


def test_folded_detail_is_still_bound_to_evidence():
    """화면에서 접었다고 출처가 없어지지 않는다."""
    import evidence as evidence_mod
    from models import VillageCard
    card = VillageCard(gu_id="X", gu_name="지구", sido="충청북도", sigungu="충주시",
                       village_resources_detail={"자연": [SOIL]})
    ev = evidence_mod.build_evidence(card)
    assert any("통계성 항목" in e.field for e in ev)
    assert evidence_mod.is_fully_bound(card, ev)


ROCK = "암석 자갈이 없음 : 847 자갈이 있음 : 272 둥근바위가 있음 : 11 바위가 있음 : 153 기타 : 37 합계 : 1,320"


def test_short_statistic_table_is_also_folded():
    """🔴 첫 판은 "150자 이상"을 요구해 이 66자짜리 표가 빠져나갔다.

    길이는 통계의 특징이 아니다 — "라벨 : 숫자" 반복이 특징이다.
    """
    assert orchestrator.is_statistic_dump(ROCK), len(ROCK)


def test_climate_line_with_one_number_is_kept():
    """숫자가 있다고 다 표는 아니다 — 콜론-숫자 쌍이 적으면 문장이다."""
    assert not orchestrator.is_statistic_dump(
        "■ 온난 다우한 기후 ■ 연평균기온 : 12.3℃ 연강수량 1,967.0mm 내외 (다우지역)")


def test_visible_resources_are_capped():
    """정상 항목이라도 카드 한 장이 감당할 수 있는 수가 있다.

    앙성은 13건이라 카드가 1,400px를 넘었다. 상한을 넘는 만큼은 접되
    같은 details 안에 그대로 남는다 — 잃는 정보는 없다.
    """
    many = {"생산·경제": [f"- 항목 {i}" for i in range(10)]}
    main, detail = orchestrator._clean_resources(many)
    assert sum(len(v) for v in main.values()) == orchestrator.VISIBLE_RESOURCES
    assert sum(len(v) for v in detail.values()) == 10 - orchestrator.VISIBLE_RESOURCES


def test_nothing_is_lost_when_folding():
    """접기 전후 항목 총수가 같아야 한다 — 하나라도 사라지면 원문 훼손이다."""
    src = {"생산·경제": [f"- 항목 {i}" for i in range(9)], "자연": [ROCK, SOIL, "- 우산보"]}
    main, detail = orchestrator._clean_resources(src)
    before = sum(len(v) for v in src.values())
    after = sum(len(v) for v in (main or {}).values()) + sum(len(v) for v in (detail or {}).values())
    assert before == after == 12


# ── 빈칸 채움말 ──

def test_placeholder_resources_are_dropped():
    """원천이 빈칸 대신 적어 넣은 말은 항목이 아니다.

    실측: '해당사항없음' '? 해당사항 없음' '특이사항 없음' '- 해당없음'.
    그대로 두면 "생산·경제 — 해당사항없음"처럼 항목인 척하는 빈 줄이 된다.
    """
    for text in ("해당사항없음", "? 해당사항 없음", "특이사항 없음", "- 해당없음", "■ 없음"):
        assert orchestrator.is_placeholder_resource(text), text


def test_specific_negatives_are_kept():
    """🔴 '특산물자원 없음'은 거르지 않는다.

    무엇을 확인했고 없었는지 말해 주므로 정보다. '해당사항없음'과 달리
    대상이 있다 — 이 둘을 같이 지우면 확인한 사실까지 잃는다.
    """
    for text in ("- 특산물자원 없음", "산업시설 없음", "경제자원이 많지는 않지만 발전 가능성 있음"):
        assert not orchestrator.is_placeholder_resource(text), text


def test_placeholder_does_not_consume_the_visible_slot():
    """빈칸 채움말이 상한 6칸 중 하나를 차지하면 진짜 항목이 밀려난다."""
    src = {"생산·경제": ["해당사항없음"] + [f"- 항목 {i}" for i in range(6)]}
    main, detail = orchestrator._clean_resources(src)
    assert sum(len(v) for v in main.values()) == 6
    assert detail is None
    assert "해당사항없음" not in str(main)


DASH_TABLE = "* 암석 자갈이 없음 - 99 자갈이 있음 - 2,178 잔자갈 있음 - 0 바위가 있음 - 3,310 합계 - 5,587"
PROSE = ("? 우동마을이 속한 군산시의 기후는 남부서안형 기후구에 속하며, 바다의 영향으로 겨울에 "
         "북서계절풍의 영향을 강하게 받아 눈이 많이 내린다. 연평균기온 13°C, 1월 평균기온 -1. 5°C, "
         "8월 평균기온 25°C이며, 연강수량은 1,200mm이다. 옥산면 남서부에 편마암으로 이루어진 "
         "용화산(龍華山:100m)·대황산(大凰山:70m) 등 해발고도 100m 내외의 산지가 있다.")
UNIT_TABLE = "?연평균기온 : 14.5℃(최고극값 33.1℃) ?연평균습도 : 75.2% ?연강수량 : 1,638.5mm"


def test_dash_separated_table_is_folded():
    """구분자가 ':'만은 아니다 — 뇌곡은 '보통답 - 0 사질답 - 20'으로 적혀 있다."""
    assert orchestrator.is_statistic_dump(DASH_TABLE)


def test_geography_prose_is_not_folded():
    """🔴 '-'를 무조건 구분자로 보면 산문이 걸린다.

    우동의 지리 서술에는 '1월 평균기온 -1. 5°C'(음수)와 '용화산(龍華山:100m)'
    (한자 병기)이 있다. 이건 마을이 어떤 곳인지 말해 주는 문장이지 표가 아니다.
    """
    assert not orchestrator.is_statistic_dump(PROSE)


def test_units_glued_to_numbers_still_count_as_a_table():
    """숫자가 단위에 붙어 있어도 '라벨 : 값'이 반복되면 표다 (달빛한옥)."""
    assert orchestrator.is_statistic_dump(UNIT_TABLE)
