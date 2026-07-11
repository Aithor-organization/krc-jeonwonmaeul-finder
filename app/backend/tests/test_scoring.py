import intent
import scoring


SALE = {"진행단계": "분양중", "분양율": 60, "계획세대수": 120, "법정동코드": "44710310", "시군구": "예산군"}
VILLAGE = {"인구": 320, "빈집수": 8, "자원": "조용함", "법정동코드": "44710310", "시군구": "예산군"}


def test_score_range_and_reasons():
    p = intent.parse("충남 분양 진행 중")
    score, grade, reasons = scoring.score_card(p, SALE, VILLAGE)
    assert 0.0 < score <= 1.0
    assert grade == "A"  # 법정동코드 직접 매칭
    assert any("진행단계" in r for r in reasons)


def test_water_not_in_score_AC4():
    """물사정 선호는 점수에 반영되지 않아야 한다 (지역 패널로만)."""
    p_water = intent.parse("물 걱정 적은 곳")           # preferences=['물사정']
    p_none = intent.parse("충남")                        # preferences=[]
    s_water, _, _ = scoring.score_card(p_water, SALE, VILLAGE)
    s_none, _, _ = scoring.score_card(p_none, SALE, VILLAGE)
    assert s_water == s_none  # 물 선호가 점수를 바꾸지 않음


def test_stage_ordering():
    p = intent.parse("충남")
    s_active, _, _ = scoring.score_card(p, {**SALE, "진행단계": "분양중"}, VILLAGE)
    s_done, _, _ = scoring.score_card(p, {**SALE, "진행단계": "분양완료"}, VILLAGE)
    assert s_active > s_done


def test_grade_c_without_village():
    p = intent.parse("충남")
    _, grade, _ = scoring.score_card(p, SALE, None)
    assert grade == "C"
