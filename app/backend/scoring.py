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

    # ── 3항: 선호매칭 ──
    prefs = list(getattr(parsed, "preferences", []) or [])
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
        elif p == "물사정":
            # 물 관심은 '지역 가뭄 패널'로 응답되므로 점수에 반영하지 않음 (AC4)
            continue
        elif p.replace("편의", "").replace("적음", "").replace("재배", "") in resources:
            pref_hits += 1
    scored_prefs = [p for p in prefs if p != "물사정"]
    pref_score = (pref_hits / len(scored_prefs)) if scored_prefs else 0.5
    if pref_hits:
        reasons.append(f"선호 조건 {pref_hits}개 부합")
    pref_basis = (
        f"선호 {len(scored_prefs)}개 중 {pref_hits}개 부합 → {pref_hits}/{len(scored_prefs)} = {pref_score:g}"
        if scored_prefs else f"선호 조건 없음 → 중립값 {pref_score}"
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
