"""Evidence 바인딩 — 모든 수치를 원천 API 필드에 연결. 미바인딩 = 차단 (AITHOR verifier 패턴, AC3)."""
from __future__ import annotations

from collections.abc import Callable

import config
from models import Evidence, VillageCard

# 카드에 실리는 값 하나 = 이 표의 한 줄. 필드를 추가하면서 여기 한 줄만 적으면
# 근거 생성(build_evidence)과 미바인딩 검사(is_fully_bound)가 자동으로 같이 움직인다.
#
# 🔴 두 함수에 따로 적으면 안 된다. 전에는 그랬고, 그래서 새 값을 화면에 올릴 때
# 근거는 붙였는데 검사 목록에 넣는 걸 잊으면 "근거 없는 수치"가 검사를 통과했다.
#
#   (카드 속성, evidence field, 값이 있는지 판정, claim 문구)
_BINDINGS: list[tuple[str, str, str, Callable[[VillageCard], str]]] = [
    ("sale_stage", config.API_SALE, "진행단계",
     lambda c: f"진행단계 {c.sale_stage}"),
    ("sale_rate", config.API_SALE, "분양율",
     lambda c: f"분양율 {c.sale_rate}%"),
    ("planned_households", config.API_SALE, "계획세대수",
     lambda c: f"계획세대수 {c.planned_households}"),
    ("population", config.API_VILLAGE, "인구",
     lambda c: f"인구 {c.population}"),
    ("vacant_houses", config.API_VILLAGE, "빈집수",
     lambda c: f"빈집수 {c.vacant_houses}"),
    # 이 항만 원천 필드가 아니라 계산값이다. 그래서 field에 산식을 적는다 —
    # "고령화율"이라고만 쓰면 API에 그런 이름의 필드가 있는 것처럼 읽힌다.
    ("elderly_ratio", config.API_VILLAGE,
     "(villMaleAge_65Cnt + villFemaleAge_65Cnt) ÷ 연령 16칸 합",
     lambda c: f"고령화율 {c.elderly_ratio}% (65세 이상 {c.elderly_count}명)"),
    ("slate_houses", config.API_VILLAGE, "villHouseSlate",
     lambda c: f"슬레이트 주택 {c.slate_houses}채"),
    ("village_note", config.API_VILLAGE, "villDescription",
     lambda c: "마을 소개 원문"),
    # 자원은 여러 필드를 접두사로만 묶은 값이라 단일 필드명을 적을 수 없다.
    # 어느 오퍼레이션에서 왔는지까지 밝힌다.
    ("village_resources", config.API_VILLAGE,
     "resourceVill · villEconomy*Resource* / villNature*Resource*",
     lambda c: "마을 자원 원문 " + str(sum(len(v) for v in c.village_resources.values())) + "건"),
]


def _present(card: VillageCard, attr: str) -> bool:
    """빈 문자열·빈 dict도 '없음'으로 본다 — 소개글이 ''인 카드에 근거를 붙일 이유가 없다."""
    value = getattr(card, attr, None)
    if value is None or value == "" or value == {}:
        return False
    return True


def build_evidence(card: VillageCard) -> list[Evidence]:
    """카드의 각 수치를 API 필드에 바인딩. 값이 있는 것만 evidence 생성."""
    tag = card.gu_name
    return [
        Evidence(claim=f"[{tag}] {claim(card)}", api=api, field=field,
                 value=getattr(card, attr))
        for attr, api, field, claim in _BINDINGS if _present(card, attr)
    ]


def is_fully_bound(card: VillageCard, evidence: list[Evidence]) -> bool:
    """카드의 노출 수치 필드가 모두 evidence에 바인딩됐는지 검증 (미바인딩 차단용)."""
    bound_fields = {e.field for e in evidence if e.claim.startswith(f"[{card.gu_name}]")}
    required = {field for attr, _, field, _ in _BINDINGS if _present(card, attr)}
    return required.issubset(bound_fields)
