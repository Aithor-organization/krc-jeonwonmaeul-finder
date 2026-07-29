"""적합도 점수 (결정론) — 물 정보는 점수에서 제외 (SPEC AC4, v3 결정).

점수 = 0.5*진행단계 + 0.3*가용성(분양율 역) + 0.2*선호매칭.

세 항의 계산은 `_terms()` 한 곳에만 있다. 점수(score_card)와 화면에 보여줄
산식 전개(score_breakdown)가 같은 함수를 쓰므로, 표시값과 실제 점수가
어긋날 수 없다 — 두 곳에 적으면 반드시 벌어진다.
"""
from __future__ import annotations

_STAGE_SCORE = {"분양중": 1.0, "분양예정": 0.6, "분양완료": 0.1}

WEIGHTS = {"진행단계": 0.5, "가용성": 0.3, "선호매칭": 0.2}
FORMULA = "0.5 × 진행단계 + 0.3 × 가용성 + 0.2 × 선호매칭"

# 판정할 수 있는 선호 — 실제로 대조할 필드가 있는 것만.
#   조용함   ← 농촌마을현황 인구
#   빈집적음 ← 농촌마을현황 빈집수
SCORABLE_PREFS = {"조용함", "빈집적음"}

# 인식은 하지만 판정할 데이터가 없는 선호.
#
# 🔴 이 목록을 분모에 넣으면 안 된다. 전에는 넣고 있었고, 대조할 필드가 없어
# 100% 미부합했다 — "강원 스마트팜 마을"이 "강원 마을"보다 0.1점 낮았다(실측
# 0.65 vs 0.75). 조건을 더 적을수록 점수가 떨어지는 셈이라, 사용자 입장에서는
# 반영된 것도 아니고 무시된 것도 아닌 최악의 상태였다.
#
# 마을 자원 서술(villDescription)로 판정하던 경로가 있었으나, 그 필드는
# 마을 연혁·지리 서술이라 선호 매칭에 쓰면 노이즈만 늘어 인덱스에서 제외했다.
# 그 결정의 결과를 여기서 정직하게 받는다 — 판정 못 하면 점수에 넣지 않는다.
UNSCORABLE_PREFS = {
    "교통편의": "도로·대중교통 데이터가 공공데이터에 없습니다",
    "스마트팜": "스마트팜 시설 정보가 공공데이터에 없습니다",
    "청년창업": "청년창업 지원 여부가 공공데이터에 없습니다",
    "과수재배": "작물 정보가 공공데이터에 없습니다",
    "축산": "축산 정보가 공공데이터에 없습니다",
    "물사정": "지역 가뭄 정보는 별도 패널로 안내하며 점수에는 넣지 않습니다",
}


def _terms(parsed, sale: dict, village: dict | None) -> tuple[list[dict], list[str]]:
    """세 항의 (값, 근거)를 계산한다. 점수와 산식 전개가 공유하는 단일 출처."""
    reasons: list[str] = []

    # ── 1항: 진행단계 ──
    stage = sale.get("진행단계")
    s_stage = _STAGE_SCORE.get(stage, 0.3)
    if stage:
        reasons.append(f"진행단계={stage}")
    stage_basis = (
        f"{stage} → {s_stage}" if stage in _STAGE_SCORE
        else f"단계 미상 → 기본값 {s_stage}"
    )

    # ── 2항: 가용성 (분양율의 역 — 덜 팔렸을수록 들어갈 자리가 많다) ──
    rate = sale.get("분양율")
    try:
        rate = float(rate) if rate is not None else None
    except (TypeError, ValueError):
        rate = None
    if rate is not None:
        rate = max(0.0, min(100.0, rate))  # 0~100 범위 보정 (점수 왜곡 방지)
        avail = (100.0 - rate) / 100.0
        reasons.append(f"분양율 {rate:g}%")
        avail_basis = f"분양율 {rate:g}% → (100−{rate:g})/100 = {avail:g}"
    else:
        avail = 0.5
        avail_basis = f"분양율 미상 → 기본값 {avail}"

    # ── 3항: 선호매칭 (판정 가능한 것만) ──
    prefs = [p for p in (getattr(parsed, "preferences", []) or []) if p in SCORABLE_PREFS]
    pref_hits = 0
    resources = ""
    vac = None
    pop = None
    if village:
        resources = " ".join(
            str(village.get(k, "")) for k in ("자원", "특징", "자연자원", "경제자원")
        )
        vac = village.get("빈집수")
        pop = village.get("인구")
    for p in prefs:
        if p == "빈집적음" and isinstance(vac, (int, float)) and vac <= 10:
            pref_hits += 1
        elif p == "조용함" and (isinstance(pop, (int, float)) and pop < 500 or "조용" in resources):
            pref_hits += 1
    # prefs는 이미 SCORABLE_PREFS로 걸러져 있으므로 판정 불가 분기가 필요 없다
    pref_score = (pref_hits / len(prefs)) if prefs else 0.5
    if pref_hits:
        reasons.append(f"선호 조건 {pref_hits}개 부합")
    pref_basis = (
        f"선호 {len(prefs)}개 중 {pref_hits}개 부합 → {pref_hits}/{len(prefs)} = {pref_score:g}"
        if prefs else f"판정 가능한 선호 조건 없음 → 중립값 {pref_score}"
    )

    terms = [
        {"label": "진행단계", "weight": WEIGHTS["진행단계"], "value": s_stage, "basis": stage_basis},
        {"label": "가용성", "weight": WEIGHTS["가용성"], "value": avail, "basis": avail_basis},
        {"label": "선호매칭", "weight": WEIGHTS["선호매칭"], "value": pref_score, "basis": pref_basis},
    ]
    for t in terms:
        t["contribution"] = round(t["weight"] * t["value"], 4)
    return terms, reasons


def score_breakdown(parsed, sale: dict, village: dict | None) -> list[dict]:
    """화면에 보여줄 산식 전개. score_card와 같은 `_terms`를 쓴다."""
    terms, _ = _terms(parsed, sale, village)
    return terms


def score_card(parsed, sale: dict, village: dict | None) -> tuple[float, str, list[str]]:
    terms, reasons = _terms(parsed, sale, village)
    score = round(sum(t["weight"] * t["value"] for t in terms), 3)

    # 신뢰도 등급 — 법정동코드 직접 매칭이면 A
    grade = "D"
    if village is None:
        grade = "C"
    elif sale.get("법정동코드") and village.get("법정동코드") == sale.get("법정동코드"):
        grade = "A"
    elif village.get("시군구") == sale.get("시군구"):
        grade = "B"
    else:
        grade = "C"

    return score, grade, reasons
