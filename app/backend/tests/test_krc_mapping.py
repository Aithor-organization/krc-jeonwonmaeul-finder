"""실 API 응답 → 내부 스키마 변환 검증 (2026-07-27 실측 값 기준)."""
import krc_mapping as km


# --- normalize_items: 포털의 item 다형성 ---
def test_normalize_items_list():
    body = {"items": {"item": [{"a": 1}, {"b": 2}]}}
    assert km.normalize_items(body) == [{"a": 1}, {"b": 2}]


def test_normalize_items_single_dict():
    """numOfRows=1이면 item이 list가 아닌 dict로 온다 (실측)."""
    body = {"items": {"item": {"a": 1}}}
    assert km.normalize_items(body) == [{"a": 1}]


def test_normalize_items_empty_string():
    """0건이면 items가 빈 문자열로 온다 (실측)."""
    assert km.normalize_items({"items": "", "totalCount": 0}) == []


def test_normalize_items_missing_and_bad_types():
    assert km.normalize_items(None) == []
    assert km.normalize_items({}) == []
    assert km.normalize_items({"items": {}}) == []
    assert km.normalize_items({"items": {"item": 123}}) == []
    # list 안 비-dict 원소는 걸러낸다
    assert km.normalize_items({"items": {"item": [{"a": 1}, "x", None]}}) == [{"a": 1}]


# --- 시도명 매핑: 이게 없으면 전남+전북 78/167건(47%)이 검색 불가 ---
def test_map_sido_administrative_merge():
    assert km.map_sido("전남광주통합특별시") == "전라남도"
    assert km.map_sido("전북특별자치도") == "전라북도"


def test_map_sido_passthrough_and_empty():
    assert km.map_sido("충청남도") == "충청남도"
    assert km.map_sido("강원특별자치도") == "강원특별자치도"
    assert km.map_sido(None) is None
    assert km.map_sido("   ") is None


# --- 진행단계 매핑: 공사단계 5종 → 분양상태 3종 ---
def test_map_stage_all_measured_values():
    assert km.map_stage("준비단계") == "분양예정"
    assert km.map_stage("기반조성공사단계") == "분양예정"
    assert km.map_stage("주택건축 준비단계") == "분양예정"
    assert km.map_stage("주택건축 단계") == "분양중"
    assert km.map_stage("건축완료후 입주단계") == "분양완료"


def test_map_stage_unknown_kept_as_is():
    """미지의 단계는 임의 변환하지 않고 원문 유지 (정직성)."""
    assert km.map_stage("신규단계") == "신규단계"
    assert km.map_stage(None) is None
    assert km.map_stage("") is None


# --- 레코드 매핑 ---
REAL_ITEM = {
    "bndeLttotHscntPer": 100,
    "emdNm": "지정면",
    "inbpnCode": "42130INS2012UA03030040001",
    "legalCode": 5113033025,
    "planHscnt": 38,
    "progrsStep": "준비단계",
    "sggNm": "원주시",
    "sidoNm": "강원특별자치도",
    "zoneName": "지정새싹",
}


def test_map_sale_item_matches_internal_schema():
    m = km.map_sale_item(REAL_ITEM)
    assert m["gu_id"] == "42130INS2012UA03030040001"
    assert m["지구명"] == "지정새싹"
    assert m["시도명"] == "강원특별자치도"
    assert m["시군구"] == "원주시"
    assert m["읍면동"] == "지정면"
    assert m["법정동코드"] == "5113033025"   # int → str 정규화
    assert m["계획세대수"] == 38
    assert m["진행단계"] == "분양예정"        # 준비단계 → 변환
    assert m["분양율"] == 100
    # 샘플 데이터와 동일한 키 집합이어야 기존 필터/스코어링이 그대로 동작
    assert set(m) == {"gu_id", "지구명", "시도명", "시군구", "읍면동",
                      "법정동코드", "계획세대수", "진행단계", "분양율"}


def test_map_households_zero_is_undisclosed():
    """계획세대수 0은 '미공개' — 0세대로 표시하면 거짓 정보 (실측 7/167건)."""
    assert km.map_households(0) is None
    assert km.map_households(38) == 38
    assert km.map_households(None) is None
    assert km.map_households("38") is None      # 문자열은 신뢰하지 않음
    assert km.map_households(True) is None      # bool은 숫자로 취급하지 않음


def test_map_sale_item_zero_households_becomes_none():
    m = km.map_sale_item({**REAL_ITEM, "planHscnt": 0})
    assert m["계획세대수"] is None


def test_map_sale_item_missing_fields():
    m = km.map_sale_item({})
    assert m["gu_id"] == "" and m["지구명"] == ""
    assert m["시도명"] is None and m["법정동코드"] is None
    assert m["진행단계"] is None


def test_map_sales_batch_and_sido_conversion():
    rows = km.map_sales([REAL_ITEM, {**REAL_ITEM, "sidoNm": "전남광주통합특별시"}])
    assert len(rows) == 2
    assert rows[1]["시도명"] == "전라남도"
