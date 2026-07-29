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
OUT = Path(__file__).resolve().parents[1] / "app" / "backend" / "data" / "village_index.json"

# 인구는 단일 필드가 아니라 성별×연령대 16칸을 합산해야 한다
AGE_FIELDS = [f"vill{g}Age_{a}Cnt" for g in ("Male", "Female")
              for a in (0, 10, 20, 30, 40, 50, 60, 65)]

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


def slim(v: dict) -> dict:
    """샘플 스키마(rural_village.json)와 같은 한글 키로 맞춘다.

    villDescription은 싣지 않는다 — '자원'처럼 보이지만 실제로는 마을 연혁·
    지리 서술이다(151건 중 선호 키워드 출현 5건, 그마저 문맥이 다름).
    선호 매칭에 넣으면 노이즈만 는다. 조용함은 인구로, 빈집적음은 빈집수로
    판정되므로 이 둘은 실데이터로 판정 가능하고, 나머지 선호는 단순히
    매칭되지 않는다(없는 근거를 지어내지 않는다).
    """
    return {
        "법정동코드": str(v.get("legalCode")),
        "마을명": v.get("villNm") or "",
        "시도명": SIDO_MAP.get(v.get("sidoNm") or "", v.get("sidoNm") or ""),
        "시군구": v.get("sggNm") or "",
        "읍면동": v.get("emdNm") or "",
        "인구": population(v),
        "빈집수": vacant_houses(v),
        "총주택수": _int(v.get("villHouseTotCnt")) or None,
    }


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

    pop_known = sum(1 for v in index.values() if v["인구"] is not None)
    vac_known = sum(1 for v in index.values() if v["빈집수"] is not None)
    print(f"\n지구 매칭 {matched_districts}/{len(sale)}건 ({matched_districts/len(sale)*100:.0f}%)"
          f" · 마을 {matched_villages}곳 (코드 중복 제거)")
    matched = matched_villages
    print(f"  인구 확인 가능 {pop_known}건 · 미입력 {matched - pop_known}건")
    print(f"  빈집 확인 가능 {vac_known}건 · 미입력 {matched - vac_known}건")

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
