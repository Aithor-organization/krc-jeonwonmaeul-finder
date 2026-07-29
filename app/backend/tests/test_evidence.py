import evidence as evidence_mod
from models import VillageCard


def make_card():
    return VillageCard(
        gu_id="g1", gu_name="예산 대흥 전원마을", sido="충청남도", sigungu="예산군",
        eupmyeon="대흥면", sale_stage="분양중", sale_rate=60, planned_households=120,
        population=320, vacant_houses=8, score=0.7, confidence_grade="A",
    )


def test_build_and_fully_bound_AC3():
    """근거 표의 '원본 필드' 열에는 **실제 API 필드명**이 들어가야 한다.

    🔴 전에는 '진행단계' '분양율' 같은 우리 내부 한글 이름을 넣고 열 제목만
    "원본 필드"라고 붙여 놨다. 원천을 확인하러 간 사람은 그런 이름을 못 찾는다.
    """
    card = make_card()
    ev = evidence_mod.build_evidence(card)
    fields = {e.field for e in ev}
    assert {"progrsStep", "bndeLttotHscntPer", "planHscnt", "villHouseEmpty"}.issubset(fields)
    # 인구는 단일 필드가 아니라 16칸 합이라 산식을 적는다
    assert any("Age_*Cnt" in f for f in fields), fields
    assert evidence_mod.is_fully_bound(card, ev)


def test_source_stage_label_is_shown_next_to_ours():
    """'분양중'은 우리 이름이고 원천은 '주택건축 단계'다 — 대응이 보여야 한다."""
    card = make_card()
    card.sale_stage_source = "주택건축 단계"
    hit = next(e for e in evidence_mod.build_evidence(card) if e.field == "progrsStep")
    assert "분양중" in hit.claim and "주택건축 단계" in hit.claim


def test_unbound_detected():
    card = make_card()
    ev = evidence_mod.build_evidence(card)
    ev = [e for e in ev if e.field != "bndeLttotHscntPer"]  # 근거 제거 → 미바인딩
    assert not evidence_mod.is_fully_bound(card, ev)


def test_missing_field_not_required():
    card = make_card()
    card.vacant_houses = None  # 값 없으면 근거 불필요
    ev = evidence_mod.build_evidence(card)
    assert evidence_mod.is_fully_bound(card, ev)
    assert all(e.field != "빈집수" for e in ev)
