"""Evidence 바인딩 — 모든 수치를 원천 API 필드에 연결. 미바인딩 = 차단 (AITHOR verifier 패턴, AC3)."""
from __future__ import annotations

import config
from models import Evidence, VillageCard


def build_evidence(card: VillageCard) -> list[Evidence]:
    """카드의 각 수치를 API 필드에 바인딩. 값이 있는 것만 evidence 생성."""
    ev: list[Evidence] = []
    tag = card.gu_name
    if card.sale_stage is not None:
        ev.append(Evidence(claim=f"[{tag}] 진행단계 {card.sale_stage}",
                            api=config.API_SALE, field="진행단계", value=card.sale_stage))
    if card.sale_rate is not None:
        ev.append(Evidence(claim=f"[{tag}] 분양율 {card.sale_rate}%",
                            api=config.API_SALE, field="분양율", value=card.sale_rate))
    if card.planned_households is not None:
        ev.append(Evidence(claim=f"[{tag}] 계획세대수 {card.planned_households}",
                            api=config.API_SALE, field="계획세대수", value=card.planned_households))
    if card.population is not None:
        ev.append(Evidence(claim=f"[{tag}] 인구 {card.population}",
                            api=config.API_VILLAGE, field="인구", value=card.population))
    if card.vacant_houses is not None:
        ev.append(Evidence(claim=f"[{tag}] 빈집수 {card.vacant_houses}",
                            api=config.API_VILLAGE, field="빈집수", value=card.vacant_houses))
    return ev


def is_fully_bound(card: VillageCard, evidence: list[Evidence]) -> bool:
    """카드의 노출 수치 필드가 모두 evidence에 바인딩됐는지 검증 (미바인딩 차단용)."""
    bound_fields = {e.field for e in evidence if e.claim.startswith(f"[{card.gu_name}]")}
    required: set[str] = set()
    if card.sale_stage is not None:
        required.add("진행단계")
    if card.sale_rate is not None:
        required.add("분양율")
    if card.planned_households is not None:
        required.add("계획세대수")
    if card.population is not None:
        required.add("인구")
    if card.vacant_houses is not None:
        required.add("빈집수")
    return required.issubset(bound_fields)
