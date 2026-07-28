"""KRC 실 API 응답 → 내부 스키마 변환 (기술명세 §3.2).

실 API는 영문 camelCase 필드와 **공사 진행단계**를 반환한다. 내부 코드·샘플은
한글 필드와 **분양 상태**(분양중/분양예정/분양완료)를 쓰므로 경계에서 변환한다.
매핑 근거는 2026-07-27 전국 167건 전수 실측(진행단계 5종·시도 9종).
"""
from __future__ import annotations

# 공사 진행단계(실측 5종) → 분양 상태(서비스 3종)
STAGE_MAP: dict[str, str] = {
    "준비단계": "분양예정",
    "기반조성공사단계": "분양예정",
    "주택건축 준비단계": "분양예정",
    "주택건축 단계": "분양중",
    "건축완료후 입주단계": "분양완료",
}

# API 시도명(행정통합 반영) → 서비스 표준 시도명(intent 파서 산출값과 동일해야 매칭됨).
# 이 매핑이 없으면 전남(56건)·전북(22건) = 전체의 47%가 검색되지 않는다.
SIDO_MAP: dict[str, str] = {
    "전남광주통합특별시": "전라남도",
    "전북특별자치도": "전라북도",
}

# 변환 사실을 사용자에게 고지 (정직성 — 원천 값과 표시 값이 다르므로)
STAGE_NOTE = (
    "진행단계는 KRC 공사단계를 분양상태로 변환한 값입니다"
    " (준비·기반조성·주택건축 준비→분양예정, 주택건축→분양중, 건축완료후 입주→분양완료)."
)
VILLAGE_NOTE = (
    "live-mode에서는 마을 상세(인구·빈집수)를 제공하지 않습니다"
    " — 농촌마을현황 데이터가 전국 2.8만 건 규모라 별도 조인 설계가 필요합니다."
)


def normalize_items(body: dict | None) -> list[dict]:
    """items.item을 항상 list로 정규화.

    공공데이터포털은 결과가 1건이면 item을 list가 아닌 dict로 반환한다(실측).
    0건이면 items가 빈 문자열("")로 온다.
    """
    if not isinstance(body, dict):
        return []
    items = body.get("items")
    if not isinstance(items, dict):
        return []
    item = items.get("item")
    if item is None:
        return []
    if isinstance(item, dict):
        return [item]
    if isinstance(item, list):
        return [x for x in item if isinstance(x, dict)]
    return []


def map_sido(name: object) -> str | None:
    if name is None:
        return None
    s = str(name).strip()
    if not s:
        return None
    return SIDO_MAP.get(s, s)


def map_stage(step: object) -> str | None:
    """공사단계 → 분양상태. 미지의 값은 원문 유지(임의 변환보다 정직)."""
    if step is None:
        return None
    s = str(step).strip()
    if not s:
        return None
    return STAGE_MAP.get(s, s)


def map_households(value: object) -> int | None:
    """계획세대수. 0은 '미공개'로 보고 None 처리 (실측 7/167건).

    준비단계 지구가 '0세대 계획'일 수는 없다 — 0을 그대로 노출하면 거짓 정보가
    되므로 미바인딩(확인 불가)으로 넘긴다.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return int(value) or None


def map_sale_item(raw: dict) -> dict:
    """전원마을 분양정보 1건 → 내부 한글 스키마 (샘플 데이터와 동일 키)."""
    return {
        "gu_id": str(raw.get("inbpnCode") or ""),
        "지구명": str(raw.get("zoneName") or ""),
        "시도명": map_sido(raw.get("sidoNm")),
        "시군구": str(raw.get("sggNm") or ""),
        "읍면동": raw.get("emdNm"),
        "법정동코드": str(raw.get("legalCode")) if raw.get("legalCode") is not None else None,
        "계획세대수": map_households(raw.get("planHscnt")),
        "진행단계": map_stage(raw.get("progrsStep")),
        "분양율": raw.get("bndeLttotHscntPer"),
    }


def map_sales(raw_items: list[dict]) -> list[dict]:
    return [map_sale_item(r) for r in raw_items]
