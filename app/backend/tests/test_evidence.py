import evidence as evidence_mod
from models import VillageCard


def make_card():
    return VillageCard(
        gu_id="g1", gu_name="예산 대흥 전원마을", sido="충청남도", sigungu="예산군",
        eupmyeon="대흥면", sale_stage="분양중", sale_rate=60, planned_households=120,
        population=320, vacant_houses=8, score=0.7, confidence_grade="A",
    )


def test_build_and_fully_bound_AC3():
    card = make_card()
    ev = evidence_mod.build_evidence(card)
    fields = {e.field for e in ev}
    assert {"진행단계", "분양율", "계획세대수", "인구", "빈집수"}.issubset(fields)
    assert evidence_mod.is_fully_bound(card, ev)


def test_unbound_detected():
    card = make_card()
    ev = evidence_mod.build_evidence(card)
    ev = [e for e in ev if e.field != "분양율"]  # 근거 제거 → 미바인딩
    assert not evidence_mod.is_fully_bound(card, ev)


def test_missing_field_not_required():
    card = make_card()
    card.vacant_houses = None  # 값 없으면 근거 불필요
    ev = evidence_mod.build_evidence(card)
    assert evidence_mod.is_fully_bound(card, ev)
    assert all(e.field != "빈집수" for e in ev)
