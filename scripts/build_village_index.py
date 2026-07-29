#!/usr/bin/env python3
"""농촌마을현황(28,342건) → 분양지구에 붙는 마을만 추린 인덱스 생성.

왜 사전 빌드인가:
  이 API는 서버 필터가 없다 — sidoNm/sggNm/legalCode 어느 파라미터를 줘도
  전건(28,342)이 그대로 온다 (2026-07-29 실측). 전량 수신은 13초/31MB라
  요청 때마다 할 수 없고, 서버리스 함수 메모리에도 부담이다.

  그런데 실제로 필요한 건 분양지구 167곳의 법정동코드뿐이다. 그중 151건이
  마을 데이터와 완전일치한다(90%). 그 151건만 뽑으면 인덱스는 수십 KB로 줄고
  런타임 조회는 즉시 끝난다.

  대가는 스냅샷이라는 점이다. 농촌마을현황은 연 단위 조사 자료라 스냅샷이
  타당하지만, **생성 시각을 함께 기록하고 화면에 고지한다** — 언제 기준인지
  모르는 수치는 근거가 아니다.

사용법:
    KRC_SERVICE_KEY=... python3 scripts/build_village_index.py
    python3 scripts/build_village_index.py --dry-run   # 파일 안 쓰고 통계만
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

SALE_URL = "https://apis.data.go.kr/B552149/raiseSaleVill/saleVill"
VILL_URL = "https://apis.data.go.kr/B552149/raiseRuralVill/infoVill"
# 마을 자원정보. 전건 조회가 안 되고 villId를 하나씩 넣어야 한다(파라미터 없이
# 부르면 400). 런타임에는 못 할 일이지만 빌드 때는 127회면 끝난다.
RESOURCE_URL = "https://apis.data.go.kr/B552149/raiseRuralVill/resourceVill"
OUT = Path(__file__).resolve().parents[1] / "app" / "backend" / "data" / "village_index.json"

# 인구는 단일 필드가 아니라 성별×연령대 16칸을 합산해야 한다
AGE_FIELDS = [f"vill{g}Age_{a}Cnt" for g in ("Male", "Female")
              for a in (0, 10, 20, 30, 40, 50, 60, 65)]
ELDER_FIELDS = ["villMaleAge_65Cnt", "villFemaleAge_65Cnt"]

# 마을 소개글 상한. 원문 평균 244자·최장 2,000자대라 그대로 실으면 인덱스가
# 부풀고 카드도 읽히지 않는다. 자르되 잘랐다는 사실을 화면에 표시한다.
DESC_MAX = 400

SIDO_MAP = {"전남광주통합특별시": "전라남도", "전북특별자치도": "전라북도"}


def fetch(url: str, rows: int, key: str) -> list[dict]:
    r = httpx.get(url, params={"serviceKey": key, "pageNo": 1,
                               "numOfRows": rows, "dataType": "json"}, timeout=300)
    r.raise_for_status()
    body = r.json()["response"]["body"]
    items = (body.get("items") or {}).get("item") or []
    return items if isinstance(items, list) else [items]


def _int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def population(v: dict) -> int | None:
    """인구. 0은 미입력으로 본다.

    실측 근거: 매칭 151건 중 38건이 인구 0인데, 그중 32건은 총주택수도 0이고
    나머지 6건은 주택이 있다(원주 서곡10리는 200채인데 인구 0). 집이 200채인
    마을에 사람이 0명일 수는 없으므로 이 0은 조사 미입력이다.
    """
    total = sum(_int(v.get(k)) for k in AGE_FIELDS)
    return total or None


def vacant_houses(v: dict) -> int | None:
    """빈집수. 0은 그대로 살린다 — 단, 마을 자체가 미입력이면 신뢰하지 않는다.

    인구 0과 달리 '빈집이 없는 마을'은 실재한다 (인구·주택이 모두 잡힌 67건이
    빈집 0). 다만 인구도 주택수도 0으로 비어 있는 레코드의 빈집 0은
    "빈집이 없다"가 아니라 "아무것도 입력되지 않았다"이므로 미상 처리한다.
    """
    if population(v) is None and _int(v.get("villHouseTotCnt")) == 0:
        return None
    return _int(v.get("villHouseEmpty"))


def elderly_ratio(v: dict) -> tuple[int | None, int | None]:
    """(65세 이상 인원, 고령화율 %). 인구가 미입력이면 둘 다 None.

    이 마을에서 살 만한가를 가장 잘 말해 주는 수치인데도 우리는 연령 16칸을
    더해 "인구 N명" 하나로 뭉개고 버리고 있었다. 실측하면 편차가 크다 —
    봉산 90%, 교원4리 5%, 중앙값 31%. "인구 61명"과 "61명 중 55명이 65세 이상"은
    귀농을 준비하는 사람에게 전혀 다른 정보다.
    """
    total = population(v)
    if total is None:
        return None, None
    elders = sum(_int(v.get(k)) for k in ELDER_FIELDS)
    return elders, round(elders / total * 100)


def description(v: dict) -> tuple[str | None, bool]:
    """(마을 소개, 잘렸는지). 원천 villDescription을 공백 정규화만 하고 싣는다.

    전에는 이 필드를 통째로 버렸다. '자원'으로 쓰려다 마을 연혁·지리 서술이라
    선호 매칭에 노이즈만 는다고 판단한 것인데, 판단은 맞았지만 처분이 과했다.
    **선호 매칭에 못 쓴다는 것과 사람이 읽을 가치가 없다는 것은 다르다** —
    이 마을이 어떤 곳인지 말해 주는 유일한 서술 정보다(127곳 중 83곳 보유).

    선호 점수에는 여전히 넣지 않는다. 읽을거리로만 쓴다.
    """
    raw = " ".join(str(v.get("villDescription") or "").split())
    if not raw:
        return None, False
    if len(raw) > DESC_MAX:
        return raw[:DESC_MAX].rstrip(), True
    return raw, False


def slate_houses(v: dict) -> int | None:
    """슬레이트(석면 우려) 주택 수. **0은 싣지 않는다.**

    0이 '없음'인지 '미조사'인지 구분할 방법이 없다. 127곳 중 36곳만 1 이상이고
    나머지 91곳의 0을 "석면 없음"으로 보이면 안 하느니만 못한 안심을 준다.
    값이 있을 때만 알리고, 없으면 침묵한다 — 이 프로젝트의 0=미입력 원칙 그대로.
    """
    n = _int(v.get("villHouseSlate"))
    return n or None


def slim(v: dict) -> dict:
    """샘플 스키마(rural_village.json)와 같은 한글 키로 맞춘다.

    주택 연식(villHouseYear_*)은 **의도적으로 제외**한다. 127곳 중 57곳에 값이
    있지만 5칸의 합이 총주택수와 맞는 경우가 23/57(40%)뿐이라, 구간 라벨
    (_5/_9/_10/_20/_30)이 무엇을 뜻하는지 원천 문서 없이는 확정할 수 없다.
    "30년 이상 N채"라고 썼다가 라벨 의미가 다르면 그건 추측을 사실로 파는 것이다.
    """
    elders, elder_ratio = elderly_ratio(v)
    desc, truncated = description(v)
    return {
        "법정동코드": str(v.get("legalCode")),
        "마을ID": str(v.get("villId") or "") or None,
        "마을명": v.get("villNm") or "",
        "시도명": SIDO_MAP.get(v.get("sidoNm") or "", v.get("sidoNm") or ""),
        "시군구": v.get("sggNm") or "",
        "읍면동": v.get("emdNm") or "",
        "인구": population(v),
        "65세이상": elders,
        "고령화율": elder_ratio,
        "빈집수": vacant_houses(v),
        "총주택수": _int(v.get("villHouseTotCnt")) or None,
        "슬레이트주택": slate_houses(v),
        "마을소개": desc,
        "마을소개_잘림": truncated,
    }


def fetch_resources(vill_id: str, key: str) -> dict[str, list[str]]:
    """마을 하나의 자원정보. 실패하면 조용히 빈 값 — 빌드를 세우지 않는다.

    묶는 기준은 **필드명 접두사뿐이다**(villEconomy* / villNature*). 개별 항목이
    농산물인지 특산물인지 관광자원인지는 원천 문서 없이 확정할 수 없고, 값 안에
    "■ 농산물 :" 처럼 스스로 밝히는 경우도 있어 우리가 라벨을 붙이면 그 순간
    추측이 된다. Economy/Nature는 필드명 자체가 말해 주므로 그것만 쓴다.
    """
    try:
        r = httpx.get(RESOURCE_URL, params={"serviceKey": key, "pageNo": 1,
                                            "numOfRows": 100, "dataType": "json",
                                            "villId": vill_id}, timeout=30)
        body = (r.json().get("response") or {}).get("body") or {}
    except Exception:
        return {}
    items = body.get("items")
    items = (items or {}).get("item") if isinstance(items, dict) else None
    if not items:
        return {}
    if not isinstance(items, list):
        items = [items]

    out: dict[str, list[str]] = {}
    for rec in items:
        for field, raw in rec.items():
            text = " ".join(str(raw or "").split())
            # 원천이 '값 없음'을 빈 문자열과 "-" 두 가지로 쓴다
            if not text or text == "-":
                continue
            if field.startswith("villEconomy"):
                group = "생산·경제"
            elif field.startswith("villNature"):
                group = "자연"
            else:
                continue  # villNm/villType은 이미 있거나 자원이 아니다
            if text not in out.setdefault(group, []):
                out[group].append(text)
    return {g: v for g, v in out.items() if v}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 통계만 출력")
    args = ap.parse_args()

    key = os.environ.get("KRC_SERVICE_KEY")
    if not key:
        print("KRC_SERVICE_KEY 환경변수가 필요합니다.", file=sys.stderr)
        return 1

    print("분양정보 조회…", flush=True)
    sale = fetch(SALE_URL, 500, key)
    print(f"  {len(sale)}건")

    print("농촌마을현황 조회… (28,342건 · 약 13초)", flush=True)
    vill = fetch(VILL_URL, 30000, key)
    print(f"  {len(vill)}건")

    by_code = {str(v.get("legalCode")): v for v in vill}
    wanted = {str(s.get("legalCode")) for s in sale}

    # 법정동코드 완전일치만 쓴다. 읍면동(앞 8자리)까지 내려가면 99%가 붙지만
    # 읍면동당 마을이 중앙값 22개라 그중 하나를 고르는 건 근거가 아니라 추측이다.
    index = {c: slim(by_code[c]) for c in sorted(wanted) if c in by_code}

    print(f"마을 자원정보 조회… ({len(index)}회 · 마을당 1회)", flush=True)
    with_res = 0
    for code, v in index.items():
        res = fetch_resources(v["마을ID"], key) if v.get("마을ID") else {}
        v["자원목록"] = res or None
        with_res += bool(res)
    print(f"  자원 보유 {with_res}/{len(index)}곳")

    # 🔴 두 수를 구분한다 — 섞으면 고지 문구가 틀린다.
    #   villages = 인덱스에 담긴 마을 수 (법정동코드 기준, 중복 제거)
    #   matched_districts = 실제로 마을이 붙는 분양지구 수 (여러 지구가 한 코드를 공유)
    matched_villages = len(index)
    matched_districts = sum(1 for s in sale if str(s.get("legalCode")) in index)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_api": "15104291",
        "source_total": len(vill),
        "sale_districts": len(sale),
        "matched_districts": matched_districts,
        "matched_villages": matched_villages,
        "match_rate": round(matched_districts / len(sale), 4) if sale else 0,
        "join_key": "법정동코드 완전일치 (10자리)",
        "villages": index,
    }

    print(f"\n지구 매칭 {matched_districts}/{len(sale)}건 ({matched_districts/len(sale)*100:.0f}%)"
          f" · 마을 {matched_villages}곳 (코드 중복 제거)")
    matched = matched_villages
    # 커버리지는 화면 고지 문구의 근거다 — 짐작하지 말고 매 빌드마다 다시 센다.
    coverage = {k: sum(1 for v in index.values() if v.get(k) is not None)
                for k in ("인구", "고령화율", "빈집수", "총주택수",
                          "슬레이트주택", "마을소개", "자원목록")}
    payload["field_coverage"] = coverage
    for k, n in coverage.items():
        print(f"  {k:<8} {n:>3}/{matched} ({n/matched*100:.0f}%)")

    ratios = sorted(v["고령화율"] for v in index.values() if v["고령화율"] is not None)
    if ratios:
        mid = ratios[len(ratios) // 2]
        print(f"  고령화율 최저 {ratios[0]}% · 중앙값 {mid}% · 최고 {ratios[-1]}%")

    raw = json.dumps(payload, ensure_ascii=False, indent=1)
    print(f"  인덱스 크기 {len(raw.encode())/1024:.0f}KB")

    if args.dry_run:
        print("\n--dry-run: 파일을 쓰지 않았습니다.")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(raw + "\n", encoding="utf-8")
    print(f"\n기록: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
