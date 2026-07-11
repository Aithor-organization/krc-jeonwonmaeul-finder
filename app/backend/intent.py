"""결정론적 자연어 조건 파서 (기술명세 §4, LLM 불필요 — 키 없이 동작).

지역/예산/진행단계/세대수/선호를 규칙으로 추출한다. 환각 0.
"""
from __future__ import annotations

import re

from models import ParsedQuery, Region

# 시도 별칭 → 표준명 (긴 별칭 우선 매칭)
_SIDO_ALIASES: dict[str, str] = {
    "서울특별시": "서울특별시", "서울": "서울특별시",
    "부산광역시": "부산광역시", "부산": "부산광역시",
    "대구광역시": "대구광역시", "대구": "대구광역시",
    "인천광역시": "인천광역시", "인천": "인천광역시",
    "광주광역시": "광주광역시", "광주": "광주광역시",
    "대전광역시": "대전광역시", "대전": "대전광역시",
    "울산광역시": "울산광역시", "울산": "울산광역시",
    "세종특별자치시": "세종특별자치시", "세종": "세종특별자치시",
    "경기도": "경기도", "경기": "경기도",
    "강원특별자치도": "강원특별자치도", "강원도": "강원특별자치도", "강원": "강원특별자치도",
    "충청북도": "충청북도", "충북": "충청북도",
    "충청남도": "충청남도", "충남": "충청남도",
    "전라북도": "전라북도", "전북특별자치도": "전라북도", "전북": "전라북도",
    "전라남도": "전라남도", "전남": "전라남도",
    "경상북도": "경상북도", "경북": "경상북도",
    "경상남도": "경상남도", "경남": "경상남도",
    "제주특별자치도": "제주특별자치도", "제주도": "제주특별자치도", "제주": "제주특별자치도",
}
# 긴 것부터 매칭 (충청남도가 충남/충청보다 먼저)
_SIDO_KEYS = sorted(_SIDO_ALIASES.keys(), key=len, reverse=True)

# label ← 트리거 문구들 (부분문자열 오탐 방지: "물"은 "건물/동물"에 걸리지 않도록 구체 문구만)
_PREF_KEYWORDS: list[tuple[list[str], str]] = [
    (["조용", "한적"], "조용함"),
    (["교통", "접근성"], "교통편의"),
    (["스마트팜"], "스마트팜"),
    (["청년"], "청년창업"),
    (["빈집"], "빈집적음"),
    (["물 걱정", "물걱정", "물 사정", "물사정", "농업용수", "용수"], "물사정"),
    (["과수"], "과수재배"),
    (["축산"], "축산"),
]


def _parse_sido(text: str) -> str | None:
    for key in _SIDO_KEYS:
        if key in text:
            return _SIDO_ALIASES[key]
    return None


def _parse_budget(text: str) -> int | None:
    """소수 억(1.5억), 억+천/만 복합(1억5천, 1억 5000만), 단독 만/천만 처리."""
    won = 0
    found = False
    m = re.search(r"(\d+(?:\.\d+)?)\s*억", text)
    if m:
        won += int(round(float(m.group(1)) * 100_000_000))
        found = True
        # 억 뒤의 천(5천→5천만) 또는 만(5000만)
        after = re.search(r"억\s*(\d[\d,]*)\s*천", text)
        if after:
            won += int(after.group(1).replace(",", "")) * 10_000_000
        else:
            after_m = re.search(r"억\s*(\d[\d,]*)\s*만", text)
            if after_m:
                won += int(after_m.group(1).replace(",", "")) * 10_000
        return won
    m = re.search(r"(\d[\d,]*)\s*천\s*만", text)
    if m:
        return int(m.group(1).replace(",", "")) * 10_000_000
    m = re.search(r"(\d[\d,]*)\s*만\s*원?", text)
    if m:
        return int(m.group(1).replace(",", "")) * 10_000
    return None


def _parse_stage(text: str) -> list[str]:
    # '분양' 문맥을 요구해 임의 문장의 '예정/완료' 오탐 방지
    stages: list[str] = []
    if re.search(r"분양\s*중|진행\s*중", text):
        stages.append("분양중")
    if re.search(r"분양\s*예정", text):
        stages.append("분양예정")
    if re.search(r"분양\s*완료", text):
        stages.append("분양완료")
    return stages


def _parse_household_min(text: str) -> int | None:
    m = re.search(r"(\d+)\s*세대\s*이상", text)
    return int(m.group(1)) if m else None


def _parse_preferences(text: str) -> list[str]:
    found: list[str] = []
    for triggers, label in _PREF_KEYWORDS:
        if label not in found and any(t in text for t in triggers):
            found.append(label)
    return found


def parse(text: str | None) -> ParsedQuery:
    raw = text or ""
    sido = _parse_sido(raw)
    budget = _parse_budget(raw)
    stages = _parse_stage(raw)
    hh = _parse_household_min(raw)
    prefs = _parse_preferences(raw)

    parsed_signals = sum(
        1 for x in (sido, budget, stages or None, prefs or None) if x
    )
    confidence = round(min(1.0, 0.25 * parsed_signals + (0.1 if raw.strip() else 0.0)), 2)

    return ParsedQuery(
        region=Region(sido=sido, sigungu=None),
        budget_max_krw=budget,
        sale_stage=stages,
        household_min=hh,
        preferences=prefs,
        confidence=confidence,
        raw=raw,
    )
