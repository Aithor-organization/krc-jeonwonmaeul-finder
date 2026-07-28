"""KRC OpenAPI 실호출 (live-mode). SSRF allowlist + 타임아웃 + 실패 전파.

호출 실패·비정상 응답은 예외로 올려 clients.py가 샘플 fallback을 결정하게 한다
(여기서 조용히 빈 리스트를 반환하면 "데이터 없음"과 "호출 실패"가 구분되지 않는다).
엔드포인트는 2026-07-27 실호출로 확정 (기술명세 §14 미확정 항목 해소).
"""
from __future__ import annotations

import httpx

import config
import guards
from krc_mapping import normalize_items

SALE_URL = "https://apis.data.go.kr/B552149/raiseSaleVill/saleVill"

# 전원마을 분양정보 전국 총건수는 167건(2026-07-27 실측)이라 1회 조회로 전량 수신 가능.
# 상한을 넉넉히 잡되 무한정은 아님 — 응답 폭증 방어.
MAX_ROWS = 500


class KrcApiError(RuntimeError):
    """KRC API 호출 실패 (네트워크·HTTP·비정상 resultCode)."""


def _check_host(url: str) -> None:
    if not guards.is_allowed_host(url):
        raise KrcApiError(f"허용되지 않은 호스트: {url}")


def fetch_sales(service_key: str, rows: int = MAX_ROWS) -> list[dict]:
    """전원마을 분양정보 전량 조회 → raw item 리스트. 실패 시 KrcApiError."""
    _check_host(SALE_URL)
    params = {
        "serviceKey": service_key,
        "pageNo": 1,
        "numOfRows": rows,
        "dataType": "json",
    }
    try:
        r = httpx.get(SALE_URL, params=params, timeout=config.HTTP_TIMEOUT_S)
        r.raise_for_status()
        payload = r.json()
    except httpx.HTTPError as e:
        raise KrcApiError(f"HTTP 오류: {type(e).__name__}: {e}") from e
    except ValueError as e:  # JSON 파싱 실패 (포털 장애 시 XML/HTML 반환)
        raise KrcApiError(f"응답 파싱 실패: {e}") from e

    resp = payload.get("response") if isinstance(payload, dict) else None
    if not isinstance(resp, dict):
        raise KrcApiError("예상과 다른 응답 구조")

    header = resp.get("header") or {}
    code = str(header.get("resultCode", ""))
    if code != "00":
        msg = header.get("resultMsg", "")
        raise KrcApiError(f"API 오류 resultCode={code}: {msg}")

    return normalize_items(resp.get("body"))
