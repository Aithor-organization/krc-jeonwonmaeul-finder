"""마을현황 API의 미사용 필드를 실제로 화면까지 태운다.

배경: 원천 `infoVill`은 마을당 32개 필드를 준다. 그런데 인덱스는 8개만 싣고
있었고, 그중 연령 16칸은 **더해서 '인구' 하나로 뭉갠 뒤 버렸다**. 그래서
봉산(인구 61명 중 55명이 65세 이상)과 교원4리(505명 중 5%)가 화면에서
똑같이 "인구 N명"으로 보였다 — 귀농을 준비하는 사람에게 그 둘은 완전히
다른 마을인데도.

여기서 지키는 선: 새로 꺼낸 값도 기존 값과 **같은 규율**을 받는다.
  · 모든 수치는 evidence에 바인딩된다 (안 되면 카드가 차단된다)
  · 0이 '없음'인지 '미입력'인지 구분 안 되면 싣지 않는다
  · 계산값은 field에 산식을 적는다 (원천에 없는 필드명을 지어내지 않는다)
"""
import json
from pathlib import Path

import evidence as evidence_mod
from fastapi.testclient import TestClient
from main import app
from models import VillageCard

client = TestClient(app)
INDEX = Path(__file__).resolve().parents[1] / "data" / "village_index.json"


def index_villages() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8"))["villages"]


# ── 인덱스가 실제로 새 필드를 담고 있는가 ──

def test_index_carries_the_fields_we_used_to_throw_away():
    """8개만 싣던 인덱스에 고령화율·소개글이 들어왔는지."""
    villages = index_villages()
    assert villages, "인덱스가 비어 있으면 아래 검사가 전부 무의미하다"
    keys = set(next(iter(villages.values())))
    for field in ("65세이상", "고령화율", "마을소개", "슬레이트주택", "마을ID"):
        assert field in keys, f"{field}가 인덱스에 없다 — 빌드 스크립트 재실행 필요"


def test_elderly_ratio_matches_its_own_parts():
    """고령화율이 인구·65세이상과 산술적으로 맞는가.

    표시값이 구성 요소와 어긋나면 근거 패널의 산식이 거짓말이 된다.
    """
    checked = 0
    for v in index_villages().values():
        if v["고령화율"] is None:
            continue
        assert v["인구"] and v["65세이상"] is not None
        assert v["고령화율"] == round(v["65세이상"] / v["인구"] * 100), v["마을명"]
        checked += 1
    assert checked >= 50, f"검증된 마을이 {checked}곳뿐 — 커버리지가 무너졌는지 확인"


def test_elderly_ratio_never_exceeds_100():
    """65세 이상이 전체 인구보다 많을 수는 없다 — 합산 로직이 틀리면 여기서 걸린다."""
    for v in index_villages().values():
        if v["고령화율"] is not None:
            assert 0 <= v["고령화율"] <= 100, (v["마을명"], v["고령화율"])


def test_zero_slate_is_dropped_not_shown_as_zero():
    """슬레이트 0은 싣지 않는다.

    0이 '석면 없음'인지 '미조사'인지 원천에서 구분되지 않는다. 91곳의 0을
    "석면 없음"으로 보여 주면 없느니만 못한 안심을 파는 것이다.
    """
    values = [v["슬레이트주택"] for v in index_villages().values()]
    assert 0 not in values, "0이 그대로 실렸다 — 미조사를 '없음'으로 보이게 된다"
    assert any(v for v in values), "전부 None이면 필드를 싣는 의미가 없다"


def test_village_note_is_capped_and_flags_when_cut():
    """소개글은 상한을 두되, 잘랐으면 잘랐다고 표시한다."""
    for v in index_villages().values():
        note = v["마을소개"]
        if note is None:
            continue
        assert len(note) <= 400, (v["마을명"], len(note))
        if len(note) == 400:
            assert v["마을소개_잘림"] is True, v["마을명"]


# ── 새 값도 evidence 규율을 받는가 ──

FULL = VillageCard(
    gu_id="X", gu_name="테스트지구", sido="충청남도", sigungu="예산군",
    population=61, elderly_count=55, elderly_ratio=90,
    slate_houses=3, village_note="조선시대에 형성된 마을이다.",
)


def test_every_new_number_is_bound_to_a_source_field():
    """새 값이 하나라도 근거 없이 화면에 나가면 안 된다."""
    ev = evidence_mod.build_evidence(FULL)
    assert evidence_mod.is_fully_bound(FULL, ev)
    fields = {e.field for e in ev}
    assert "villHouseSlate" in fields
    assert "villDescription" in fields


def test_elderly_evidence_states_the_formula_not_a_fake_field():
    """고령화율은 원천 필드가 아니라 계산값이다 — field에 산식이 보여야 한다.

    "고령화율"이라고만 적으면 API에 그런 이름의 필드가 있는 것처럼 읽힌다.
    """
    ev = evidence_mod.build_evidence(FULL)
    elderly = next(e for e in ev if "고령화율" in e.claim)
    assert "villMaleAge_65Cnt" in elderly.field
    assert "villFemaleAge_65Cnt" in elderly.field
    assert elderly.value == 90


def test_missing_values_produce_no_evidence():
    """없는 값에 근거를 붙이면 그게 곧 지어낸 근거다."""
    bare = VillageCard(gu_id="X", gu_name="빈지구", sido="강원특별자치도", sigungu="홍천군")
    ev = evidence_mod.build_evidence(bare)
    assert not [e for e in ev if "고령화율" in e.claim or "슬레이트" in e.claim]
    assert evidence_mod.is_fully_bound(bare, ev)


def test_empty_note_is_not_bound():
    """빈 문자열 소개글에 'villDescription 근거'를 붙이지 않는다."""
    card = FULL.model_copy(update={"village_note": ""})
    ev = evidence_mod.build_evidence(card)
    assert "villDescription" not in {e.field for e in ev}
    assert evidence_mod.is_fully_bound(card, ev)


def test_binding_table_covers_is_fully_bound():
    """근거 생성과 미바인딩 검사가 같은 표를 쓰는가.

    전에는 두 함수에 따로 적혀 있었다 — 새 값을 올리면서 검사 목록에 넣는 걸
    잊으면 "근거 없는 수치"가 검사를 통과한다. 표가 하나뿐임을 고정한다.
    """
    src = Path(evidence_mod.__file__).read_text(encoding="utf-8")
    assert src.count("_BINDINGS") >= 3, "표가 build/is_fully_bound 양쪽에서 쓰여야 한다"


# ── 화면까지 도달하는가 ──

def test_card_renders_elderly_ratio():
    app_js = client.get("/app.js").text
    assert "card.elderly_ratio" in app_js
    assert "65세 이상 " in app_js


def test_card_renders_the_village_description_as_a_quote():
    """소개글은 우리가 쓴 문장이 아니라 원천 텍스트다 — 인용 형태로 구분한다."""
    app_js = client.get("/app.js").text
    assert "village-desc" in app_js and "blockquote" in app_js
    assert "villDescription" in app_js, "출처 필드명을 화면에 밝혀야 한다"


def test_village_block_keeps_the_district_vs_village_warning():
    """새 값을 얹으면서 '지구가 아니라 마을 값'이라는 경고가 사라지면 안 된다.

    이 경고가 없어서 "빈집 0인데 왜 추천하냐"는 오독이 실제로 나왔다.
    문구는 이후 "분양 대상이 아니다"까지 담도록 강화됐다.
    """
    app_js = client.get("/app.js").text
    assert "이 지구가 아니라" in app_js and "기존 마을" in app_js
    assert "분양 대상이 아니며" in app_js


def test_search_response_actually_fills_the_new_fields():
    """스키마에 키가 있는 것과 값이 실리는 것은 다르다.

    🔴 이 검사의 첫 판은 `field in card`만 봤다 — Pydantic은 값이 None이어도
    키를 내보내므로 **항상 통과했다**. 그 사이 실제 응답은 고령화율이 전부
    None이었고(샘플 데이터에 필드가 없었다), 초록불이 그 사실을 덮고 있었다.
    값을 본다.
    """
    res = client.post("/api/search", json={"query": "충청남도 전원마을"})
    assert res.status_code == 200
    cards = res.json()["top"]
    assert cards, "결과가 없으면 이 검사는 아무것도 확인하지 못한다"

    filled = [c for c in cards if c.get("elderly_ratio") is not None]
    assert filled, f"고령화율이 실린 카드가 없다 (카드 {len(cards)}장)"
    for c in filled:
        assert 0 <= c["elderly_ratio"] <= 100
        assert c["elderly_count"] is not None and c["population"], c["gu_name"]
        # 화면에 뜨는 값이 스스로와 맞는지 — 응답 단계에서 한 번 더 본다
        assert c["elderly_ratio"] == round(c["elderly_count"] / c["population"] * 100)

    assert any(c.get("village_note") for c in cards), "마을 소개가 실린 카드가 없다"


def test_evidence_reaches_the_response_for_new_fields():
    """근거 목록에도 새 값이 실제로 올라오는가 (카드만 채우고 근거를 빠뜨리는 실수 차단)."""
    res = client.post("/api/search", json={"query": "충청남도 전원마을"}).json()
    fields = {e["field"] for e in res["evidence"]}
    assert any("villMaleAge_65Cnt" in f for f in fields), fields
    assert "villDescription" in fields, fields


def test_sample_mode_carries_the_same_fields_as_live():
    """오프라인(샘플) 모드가 라이브보다 빈약하면, 키 없이 여는 사람은 다른 서비스를 본다.

    실제로 이 불일치가 있었다 — 인덱스에는 고령화율이 들어갔는데 샘플에는
    없어서 샘플 모드 카드가 조용히 "인구 N명"으로만 남았다.
    """
    samples = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "samples" / "rural_village.json")
        .read_text(encoding="utf-8"))
    live_keys = set(next(iter(index_villages().values())))
    for row in samples:
        missing = (live_keys - {"마을ID", "읍면동"}) - set(row)
        assert not missing, f"{row['마을명']}에 없는 필드: {missing}"
        if row.get("고령화율") is not None:
            assert row["고령화율"] == round(row["65세이상"] / row["인구"] * 100), row["마을명"]


# ── 공개 페이지의 채움률이 실제 인덱스와 맞는가 ──

def test_published_coverage_matches_the_real_index():
    """근거 페이지에 적은 채움률이 인덱스 실측과 어긋나면, 그 페이지가 거짓말이 된다.

    이 서비스가 파는 것이 "근거 있는 사실 확인"이라 여기서 어긋나면
    기능 하나가 틀린 게 아니라 서비스의 전제가 틀린다.
    """
    villages = index_villages()
    total = len(villages)
    page = client.get("/data-evidence.html").text

    published = {"빈집수": 78, "인구": 73, "고령화율": 73,
                 "총주택수": 73, "마을소개": 65, "슬레이트주택": 28}
    for field, claimed in published.items():
        actual = round(sum(1 for v in villages.values() if v.get(field) is not None) / total * 100)
        assert actual == claimed, f"{field}: 페이지 {claimed}% vs 실측 {actual}%"
        assert f"{claimed}%" in page, f"{field} {claimed}%가 페이지에 없다"


def test_page_discloses_that_elderly_ratio_is_computed():
    """계산값을 원본 필드처럼 보이게 두지 않는다."""
    page = client.get("/data-evidence.html").text
    assert "고령화율은 원본에 없는 값" in page
    assert "villDescription" in page and "villHouseSlate" in page


# ── 마을 자원정보 (resourceVill, 13%) ──

def test_resources_are_grouped_only_by_what_the_field_name_proves():
    """묶음 라벨은 필드명이 보증하는 두 개뿐이어야 한다.

    개별 항목이 특산물인지 관광자원인지는 원천 문서 없이 확정할 수 없다.
    우리가 라벨을 붙이는 순간 그건 근거가 아니라 추측이 된다.
    """
    groups = {g for v in index_villages().values()
              for g in (v.get("자원목록") or {})}
    assert groups, "자원이 실린 마을이 하나도 없다 — 빌드가 자원 조회를 건너뛰었는지 확인"
    assert groups <= {"생산·경제", "자연"}, groups


def test_resource_placeholder_dash_is_not_stored():
    """원천은 '값 없음'을 빈 문자열과 '-' 두 가지로 쓴다 — 후자가 새면 화면에 '-'가 뜬다."""
    for v in index_villages().values():
        for items in (v.get("자원목록") or {}).values():
            assert items, "빈 목록이 남았다"
            assert "-" not in items, v["마을명"]


def test_resources_are_not_scored():
    """13%만 판정 가능한 조건을 점수에 넣으면 나머지 87%가 부당하게 깎인다.

    같은 실수를 이미 한 번 했다 — 대조할 데이터가 없는 선호 5종이 분모에 들어가
    "강원 스마트팜 마을"이 "강원 마을"보다 낮은 점수를 받았다.
    """
    import scoring
    from models import ParsedQuery
    sale = {"지구명": "테스트", "진행단계": "분양중", "법정동코드": "44710310"}
    rich = {"인구": 300, "빈집수": 5, "자원목록": {"생산·경제": ["■ 농산물 : 사과"]}}
    bare = {"인구": 300, "빈집수": 5, "자원목록": None}
    parsed = ParsedQuery(preferences=["과수재배"])
    assert (scoring.score_card(parsed, sale, rich)[0]
            == scoring.score_card(parsed, sale, bare)[0])


def test_resource_evidence_names_the_operation():
    """어느 오퍼레이션에서 온 값인지 밝힌다 — infoVill과 다른 호출이다."""
    card = FULL.model_copy(update={"village_resources": {"자연": ["■ 저수지 인접"]}})
    ev = evidence_mod.build_evidence(card)
    res = next(e for e in ev if "자원" in e.claim)
    assert "resourceVill" in res.field
    assert evidence_mod.is_fully_bound(card, ev)


def test_empty_resource_dict_is_not_bound():
    """{}에 근거를 붙이면 없는 자원에 출처를 다는 셈이다."""
    card = FULL.model_copy(update={"village_resources": {}})
    ev = evidence_mod.build_evidence(card)
    assert "resourceVill" not in " ".join(e.field for e in ev)
    assert evidence_mod.is_fully_bound(card, ev)


def test_card_renders_resources_with_source_and_scoring_disclosure():
    """자원을 보여 주되 '점수에 안 넣는다'는 사실을 같은 자리에서 밝힌다."""
    app_js = client.get("/app.js").text
    assert "village_resources" in app_js
    assert "resourceVill" in app_js
    assert "적합도 점수에는 넣지 않습니다" in app_js


def test_resource_text_passes_the_output_guard():
    """원천 자유 텍스트가 가드를 거치지 않고 화면으로 나가면 여기가 유일한 구멍이 된다."""
    import orchestrator
    dirty = {"자연": ["연락처 010-1234-5678 로 문의"]}
    cleaned = orchestrator._clean_resources(dirty)
    assert "010-1234-5678" not in str(cleaned), cleaned


def test_long_notes_are_folded_not_cut():
    """긴 소개글은 접되 잘라내지 않는다.

    마을마다 길이가 크게 달라(최장 400자) 그대로 두면 한 카드가 나머지를 밀어낸다.
    그렇다고 서버에서 더 자르면 사용자는 원문을 볼 방법이 없어진다 —
    화면에서 접고, 누르면 펼친다.
    """
    app_js = client.get("/app.js").text
    assert "desc-toggle" in app_js and "더 보기" in app_js and "접기" in app_js
    assert 'aria-expanded' in app_js, "펼침 상태를 보조기술에 알려야 한다"

    css = client.get("/results.css").text
    assert "-webkit-line-clamp" in css
    # 접힌 상태의 클램프가 펼친 상태에서 반드시 풀려야 한다
    assert ".village-desc.is-long.is-open blockquote" in css
