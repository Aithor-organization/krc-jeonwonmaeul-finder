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


def village_note(generated_at: str | None, matched_districts: int, total_districts: int) -> str:
    """마을 상세의 출처와 한계를 한 문장으로. 기준일이 없는 수치는 근거가 아니다.

    🔴 인자는 반드시 '지구 수'끼리 맞춘다. 인덱스의 마을 수(법정동코드 기준
    중복 제거)를 넘기면 분모와 단위가 달라져 "127/167개 지구"처럼 틀린 문장이 된다.
    """
    day = (generated_at or "")[:10] or "기준일 미상"
    return (
        f"마을 상세(인구·빈집수)는 농촌마을현황 {day} 스냅샷입니다"
        f" — 법정동코드가 정확히 일치하는 {matched_districts}/{total_districts}개 지구에만 표시하며,"
        " 나머지는 '확인 불가'로 둡니다 (읍면동만 같은 마을을 임의로 붙이지 않습니다)."
    )


RATE_NOTE = (
    "분양율은 원천 데이터의 84%(141/167건)가 0으로 비어 있어 대부분 '확인 불가'로 표시됩니다"
    " — 이미 입주가 끝난 지구 17건도 0으로 기록돼 있어 미입력으로 판단했습니다."
    " 이 경우 적합도의 가용성 항은 중립값으로 계산합니다."
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


def map_sale_rate(value: object) -> float | None:
    """분양율. 0과 100 초과는 '확인 불가'로 넘긴다 (map_households와 같은 원칙).

    0을 '0% 분양'으로 읽으면 안 되는 이유 — 실측 근거:
      · 167건 중 141건(84%)이 0
      · 그중 '건축완료후 입주단계'(=이미 입주)가 17건. 사람이 사는 지구가
        0% 팔렸을 수는 없으므로 이 0은 **미입력**이다
      · 원천에 150%도 1건 존재 — 필드 자체가 신뢰 구간을 벗어난다

    "아직 분양 전이라 0"과 "입력이 안 돼서 0"을 데이터로 구분할 방법이 없다.
    구분 불가한 값을 단정적 수치로 표시하면 근거 바인딩은 통과하면서
    의미만 틀리는, 가장 잡기 어려운 형태의 거짓이 된다.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    v = float(value)
    if v <= 0 or v > 100:
        return None
    return v


def out_of_range_rate(value: object) -> float | None:
    """100을 넘어 표시를 보류한 원천 값. 정상 범위면 None.

    🔴 '없음'과 '범위를 벗어남'은 다르다. 둘 다 확인 불가로 표시하더라도
    **이유가 다르면 다르게 말해야 한다** — 구례 남도는 원천에 150%가
    적혀 있는데 화면이 "원천에 값이 없음"이라고 하면 그건 사실이 아니다.

    실측: 167건 중 100 초과는 1건(남도 150%, 계획 20세대).
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    v = float(value)
    return v if v > 100 else None


def rate_status(rate: float | None, over: float | None, stage: str | None) -> str:
    """분양율을 얼마나 믿을 수 있는가 — 네 상태로 가른다.

    🔴 전에는 둘뿐이었다: 수치가 있으면 표시, 없으면 "확인 불가". 그래서
    **우리가 아는 17건이 정말 모르는 124건과 같은 칸에 들어갔다.**
    분양완료(=이미 입주) 지구는 수치가 없어도 남은 자리가 없다는 걸 알고,
    그 판단을 점수(가용성 0)에는 이미 쓰고 있으면서 화면에서만 감췄다.

    실측 근거 (167건 전수):
      · 확정 25건 — 원천에 0<값≤100
      · 추정 17건 — 건축완료후 입주단계인데 미입력. 이 단계 23건의 값 분포는
        {0: 17, 100: 6}으로 **100이 아닌 값이 하나도 없다** → 반증 사례 없음
      · 보류  1건 — 150% (남도)
      · 미상 124건

    ⚠️ 그래도 '추정'을 숫자 100%로 적지는 않는다. 100%라는 값이 분양예정
    단계에도 12건 있어서(집을 짓기 전인데) **100의 의미 자체가 확실하지 않다**.
    아는 것은 "남은 자리 없음"이라는 판정이지 "100%"라는 수치가 아니다.
    """
    if rate is not None:
        return "확정"
    if over is not None:
        return "보류"
    if stage == "분양완료":
        return "추정"
    return "미상"


def rate_anomaly(rate: float | None, stage: str | None) -> str | None:
    """단계와 수치가 서로 어긋나는 조합. 값은 그대로 두되 사실을 알린다.

    분양예정(준비/기반조성/주택건축 준비)인데 분양율 100%가 12건.
    집을 짓기도 전에 완판일 수는 있지만(사전 예약), 그렇다고 조용히 넘기면
    사용자는 이 100%를 '입주 가능'으로 읽는다. 지어내지도, 지우지도 않고
    **어긋난다는 사실만** 적는다.
    """
    if rate == 100 and stage == "분양예정":
        return "아직 분양예정 단계인데 원천에는 100%로 기록돼 있습니다"
    return None


def map_sale_item(raw: dict) -> dict:
    """전원마을 분양정보 1건 → 내부 한글 스키마 (샘플 데이터와 동일 키)."""
    rate = map_sale_rate(raw.get("bndeLttotHscntPer"))
    over = out_of_range_rate(raw.get("bndeLttotHscntPer"))
    stage = map_stage(raw.get("progrsStep"))
    return {
        "분양율_상태": rate_status(rate, over, stage),
        "분양율_이상": rate_anomaly(rate, stage),
        "분양율_범위초과": over,
        "gu_id": str(raw.get("inbpnCode") or ""),
        "지구명": str(raw.get("zoneName") or ""),
        "시도명": map_sido(raw.get("sidoNm")),
        "시군구": str(raw.get("sggNm") or ""),
        "읍면동": raw.get("emdNm"),
        "법정동코드": str(raw.get("legalCode")) if raw.get("legalCode") is not None else None,
        "계획세대수": map_households(raw.get("planHscnt")),
        "진행단계": stage,
        # 🔴 원문을 버리면 안 된다. '분양중'은 원천에서 **주택건축 단계**,
        # 즉 집을 짓고 있는 중이다. 우리 라벨만 보면 "지금 들어갈 수 있다"로
        # 읽히지만 그런 뜻이 아니다 — 원문을 나란히 보여 줘야 오해가 없다.
        "진행단계_원문": str(raw.get("progrsStep") or "") or None,
        "분양율": rate,
    }


def map_sales(raw_items: list[dict]) -> list[dict]:
    return [map_sale_item(r) for r in raw_items]
