"""LLM 기반 자연어 파서 + 모델 라우팅 (기술명세 §4.2 Option A, AITHOR routing.py 패턴).

복잡도에 따라 3개 모델로 라우팅:
  simple  → gpt-5.4-nano   (짧고 단순한 질의)
  medium  → gpt-5.4-mini   (일반)
  complex → gpt-5.6-luna   (다중 조건/긴 질의)
실패 시 결정론 파서(intent.parse)로 자동 폴백. 키는 파일/환경에서 런타임 로드(코드 미포함).
PII는 호출 전에 guards가 마스킹하므로 원식별정보는 외부 전송되지 않는다.
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request

import config
import intent
from models import ParsedQuery, Region

_API_URL = "https://api.openai.com/v1/chat/completions"

_COMPLEXITY_TOKENS = ["억", "만원", "세대", "분양", "조용", "한적", "교통", "접근성",
                      "스마트팜", "청년", "빈집", "물", "과수", "축산", "예정", "완료"]

_SYSTEM = (
    "너는 한국 귀농·전원마을 검색 질의를 구조화하는 파서다. "
    "사용자 문장에서 아래 JSON 스키마로만 답하라(설명·코드블록 금지):\n"
    '{"sido": 표준시도명 또는 null, "sigungu": 시군구명 또는 null, '
    '"budget_max_krw": 정수(원) 또는 null, '
    '"sale_stage": ["분양중"|"분양예정"|"분양완료" 중 해당], '
    '"household_min": 정수 또는 null, '
    '"preferences": ["조용함"|"교통편의"|"스마트팜"|"청년창업"|"빈집적음"|"물사정"|"과수재배"|"축산" 중 해당]}\n'
    "시도명은 반드시 표준명(예: 충남→충청남도, 전남→전라남도, 강원→강원특별자치도)으로 정규화하라. "
    "값이 없으면 null 또는 빈 배열."
)


def load_key() -> str | None:
    if config.OPENAI_KEY_ENV:
        return config.OPENAI_KEY_ENV
    try:
        with open(config.OPENAI_KEY_FILE, encoding="utf-8") as f:
            for line in f:
                if re.match(r"\s*openai api key\s*:", line, re.IGNORECASE):
                    return line.split(":", 1)[1].strip()
    except OSError:
        return None
    return None


def route_model(query: str) -> tuple[str, str]:
    """복잡도 기반 결정론적 모델 선택 (tier, model)."""
    q = (query or "").strip()
    conds = sum(1 for t in _COMPLEXITY_TOKENS if t in q) + q.count(",")
    if conds <= 1 and len(q) <= 12:
        return "simple", config.LLM_MODEL_SIMPLE
    if conds >= 4 or len(q) >= 40:
        return "complex", config.LLM_MODEL_COMPLEX
    return "medium", config.LLM_MODEL_MEDIUM


def _call(model: str, key: str, query: str) -> dict:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": query},
        ],
        "response_format": {"type": "json_object"},
        "max_completion_tokens": 300,
    }
    req = urllib.request.Request(
        _API_URL,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT_S,
                               context=ssl.create_default_context()) as r:
        d = json.loads(r.read())
    return json.loads(d["choices"][0]["message"]["content"])


def _to_parsed(raw: dict, query: str) -> ParsedQuery:
    stage = raw.get("sale_stage") or []
    prefs = raw.get("preferences") or []
    budget = raw.get("budget_max_krw")
    hh = raw.get("household_min")
    signals = sum(1 for x in (raw.get("sido"), budget, stage or None, prefs or None) if x)
    return ParsedQuery(
        region=Region(sido=raw.get("sido"), sigungu=raw.get("sigungu")),
        budget_max_krw=int(budget) if isinstance(budget, (int, float)) else None,
        sale_stage=[s for s in stage if isinstance(s, str)],
        household_min=int(hh) if isinstance(hh, (int, float)) else None,
        preferences=[p for p in prefs if isinstance(p, str)],
        confidence=round(min(1.0, 0.3 + 0.2 * signals), 2),
        raw=query,
    )


def parse(query: str) -> tuple[ParsedQuery, dict]:
    """LLM 파싱 + 메타. 실패 시 결정론 파서 폴백. 반환: (ParsedQuery, meta)."""
    tier, model = route_model(query or "")
    key = load_key()
    if not key:
        return intent.parse(query), {"model": None, "tier": tier, "fallback": True,
                                     "error": "no_api_key"}
    try:
        raw = _call(model, key, query or "")
        return _to_parsed(raw, query or ""), {"model": model, "tier": tier, "fallback": False}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:120]
        return intent.parse(query), {"model": model, "tier": tier, "fallback": True,
                                     "error": f"http_{e.code}: {detail}"}
    except Exception as e:  # 네트워크/JSON/검증 실패 → 결정론 폴백
        return intent.parse(query), {"model": model, "tier": tier, "fallback": True,
                                     "error": f"{type(e).__name__}: {e}"}
