"""적합도 점수 (결정론) — 물 정보는 점수에서 제외 (SPEC AC4, v3 결정).

점수 = 0.5*진행단계 + 0.3*가용성(분양율 역) + 0.2*선호매칭.
"""
from __future__ import annotations

_STAGE_SCORE = {"분양중": 1.0, "분양예정": 0.6, "분양완료": 0.1}


def score_card(parsed, sale: dict, village: dict | None) -> tuple[float, str, list[str]]:
    reasons: list[str] = []

    stage = sale.get("진행단계")
    s_stage = _STAGE_SCORE.get(stage, 0.3)
    if stage:
        reasons.append(f"진행단계={stage}")

    rate = sale.get("분양율")
    try:
        rate = float(rate) if rate is not None else None
    except (TypeError, ValueError):
        rate = None
    if rate is not None:
        rate = max(0.0, min(100.0, rate))  # 0~100 범위 보정 (점수 왜곡 방지)
        avail = (100.0 - rate) / 100.0
        reasons.append(f"분양율 {rate:g}%")
    else:
        avail = 0.5

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

    score = round(0.5 * s_stage + 0.3 * avail + 0.2 * pref_score, 3)

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
