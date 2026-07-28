"""live 호출 경로 — 성공/실패/SSRF를 mock으로 검증 (실 API 미호출).

맨 아래 test_real_api_call만 KRC_SERVICE_KEY가 있을 때 실제로 호출한다.
"""
import httpx
import pytest

import config
import krc_live


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _ok_payload(items):
    return {"response": {"header": {"resultCode": "00", "resultMsg": "정상"},
                         "body": {"items": {"item": items}, "totalCount": len(items)}}}


def test_fetch_sales_success(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return _Resp(_ok_payload([{"zoneName": "A"}, {"zoneName": "B"}]))

    monkeypatch.setattr(krc_live.httpx, "get", fake_get)
    rows = krc_live.fetch_sales("KEY123")

    assert [r["zoneName"] for r in rows] == ["A", "B"]
    assert captured["params"]["serviceKey"] == "KEY123"
    assert captured["params"]["dataType"] == "json"
    # FP#1 타임아웃 필수. 단 일반 5초가 아니라 이 상류 전용 상한을 쓴다 —
    # KRC는 같은 요청이 0.3~10.4초로 흔들려 5초로는 대부분 죽는다 (2026-07-28 실측).
    assert captured["timeout"] == config.KRC_FETCH_TIMEOUT_S
    assert config.KRC_FETCH_TIMEOUT_S > config.HTTP_TIMEOUT_S
    assert captured["url"].startswith("https://apis.data.go.kr/")


def test_fetch_sales_single_item(monkeypatch):
    monkeypatch.setattr(krc_live.httpx, "get",
                        lambda *a, **k: _Resp(_ok_payload({"zoneName": "solo"})))
    assert krc_live.fetch_sales("K") == [{"zoneName": "solo"}]


def test_fetch_sales_http_error(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectTimeout("timeout")
    monkeypatch.setattr(krc_live.httpx, "get", boom)
    with pytest.raises(krc_live.KrcApiError, match="HTTP 오류"):
        krc_live.fetch_sales("K")


def test_fetch_sales_bad_json(monkeypatch):
    monkeypatch.setattr(krc_live.httpx, "get",
                        lambda *a, **k: _Resp(ValueError("not json")))
    with pytest.raises(krc_live.KrcApiError, match="응답 파싱 실패"):
        krc_live.fetch_sales("K")


def test_fetch_sales_bad_structure(monkeypatch):
    monkeypatch.setattr(krc_live.httpx, "get", lambda *a, **k: _Resp({"unexpected": 1}))
    with pytest.raises(krc_live.KrcApiError, match="예상과 다른 응답 구조"):
        krc_live.fetch_sales("K")


def test_fetch_sales_error_result_code(monkeypatch):
    payload = {"response": {"header": {"resultCode": "03",
                                       "resultMsg": "잘못된 요청 파라메터 오류입니다."}}}
    monkeypatch.setattr(krc_live.httpx, "get", lambda *a, **k: _Resp(payload))
    with pytest.raises(krc_live.KrcApiError, match="resultCode=03"):
        krc_live.fetch_sales("K")


def test_ssrf_guard_blocks_non_allowlisted(monkeypatch):
    """allowlist 밖 호스트로 URL이 바뀌면 호출 전에 차단 (기술명세 §6.2)."""
    monkeypatch.setattr(krc_live, "SALE_URL", "https://evil.example.com/x")
    monkeypatch.setattr(krc_live.httpx, "get",
                        lambda *a, **k: pytest.fail("차단되지 않고 호출됨"))
    with pytest.raises(krc_live.KrcApiError, match="허용되지 않은 호스트"):
        krc_live.fetch_sales("K")


@pytest.mark.live
@pytest.mark.skipif(not config.KRC_SERVICE_KEY, reason="KRC_SERVICE_KEY 미설정")
def test_real_api_call():
    """실제 공공데이터포털 호출 (키 있을 때만)."""
    rows = krc_live.fetch_sales(config.KRC_SERVICE_KEY, rows=5)
    assert rows, "실 API가 빈 결과를 반환"
    assert "zoneName" in rows[0] and "progrsStep" in rows[0]
