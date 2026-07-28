"""BYOK(사용자 키 직접 입력) — 동작 + 유출 차단.

사용자 시크릿을 다루므로 "키가 어디로도 새지 않는다"를 테스트로 고정한다.
"""
import urllib.error

from fastapi.testclient import TestClient

import config
import llm_intent
from main import app
from orchestrator import Orchestrator

client = TestClient(app)
FAKE_KEY = "sk-proj-USER1234567890abcdefSECRET"


def _fake_parsed(q):
    import intent
    return intent.parse(q)


# --- redact: 유출 차단의 1차 방어선 ---
def test_redact_masks_key_like_strings():
    assert "USER1234567890" not in llm_intent.redact(
        f"Incorrect API key provided: {FAKE_KEY}")
    assert "sk-***" in llm_intent.redact(f"err {FAKE_KEY}")


def test_redact_keeps_other_text():
    assert llm_intent.redact("ConnectTimeout: 시간 초과") == "ConnectTimeout: 시간 초과"


def test_redact_masks_openai_self_masked_form():
    """OpenAI는 raw 키가 아니라 'sk-proj-****cdef' 형태로 되돌려준다.

    정규식에 `*`가 없으면 이 형태를 못 잡아 키 뒤 4자리가 남는다 (실측 결함).
    """
    masked = "Incorrect API key provided: sk-proj-****************cdef. You can find"
    out = llm_intent.redact(masked)
    assert "cdef" not in out
    assert "sk-***" in out


# --- 요청 키가 서버 설정보다 우선 ---
def test_request_key_takes_precedence(monkeypatch):
    seen = {}

    def fake_call(model, key, query):
        seen["key"] = key
        return {"sido": "충청남도", "sigungu": None, "budget_max_krw": None,
                "sale_stage": [], "household_min": None, "preferences": []}

    monkeypatch.setattr(config, "OPENAI_KEY_ENV", "sk-SERVER-key")
    monkeypatch.setattr(llm_intent, "_call", fake_call)

    parsed, meta = llm_intent.parse("충남 마을", api_key=FAKE_KEY)
    assert seen["key"] == FAKE_KEY          # 서버 키가 아니라 사용자 키 사용
    assert meta["fallback"] is False
    assert parsed.region.sido == "충청남도"


def test_blank_key_falls_back_to_server(monkeypatch):
    seen = {}
    monkeypatch.setattr(config, "OPENAI_KEY_ENV", "sk-SERVER-key")
    monkeypatch.setattr(llm_intent, "_call",
                        lambda m, k, q: seen.setdefault("key", k) and {} or {})
    llm_intent.parse("충남", api_key="   ")   # 공백만 → 사용자 키 없음으로 취급
    assert seen["key"] == "sk-SERVER-key"


# --- 🔴 유출 차단: meta / 응답 어디에도 키가 없어야 한다 ---
def test_meta_never_contains_key(monkeypatch):
    monkeypatch.setattr(llm_intent, "_call",
                        lambda m, k, q: {"sido": "충청남도", "sale_stage": []})
    _, meta = llm_intent.parse("충남", api_key=FAKE_KEY)
    assert FAKE_KEY not in str(meta)


def _http_error(code, body):
    import io
    return urllib.error.HTTPError("http://x", code, "err", {}, io.BytesIO(body.encode()))


def test_http_error_body_is_not_echoed(monkeypatch):
    """401 본문에 키 조각이 있어도 응답에는 상태 안내만 남는다."""
    body = f'{{"error":{{"message":"Incorrect API key provided: sk-proj-****cdef"}}}}'
    monkeypatch.setattr(llm_intent, "_call",
                        lambda m, k, q: (_ for _ in ()).throw(_http_error(401, body)))

    _, meta = llm_intent.parse("충남", api_key=FAKE_KEY)
    assert meta["fallback"] is True
    assert "cdef" not in meta["error"]          # 자체 마스킹된 뒷자리도 남으면 안 됨
    assert "Incorrect API key" not in meta["error"]   # 원문 자체를 싣지 않는다
    assert "유효하지 않" in meta["error"]        # 대신 사람이 읽는 안내


def test_http_error_reasons_by_code(monkeypatch):
    for code, needle in [(429, "한도"), (403, "사용할 수 없"), (599, "HTTP 599")]:
        monkeypatch.setattr(llm_intent, "_call",
                            lambda m, k, q, c=code: (_ for _ in ()).throw(
                                _http_error(c, "{}")))
        _, meta = llm_intent.parse("충남", api_key=FAKE_KEY)
        assert needle in meta["error"], f"{code} → {meta['error']}"


def test_api_response_never_echoes_key(monkeypatch):
    """API 401이 나도 응답 전체(JSON 문자열)에 키가 없어야 한다."""
    body = f'{{"error":"bad key {FAKE_KEY} / masked sk-proj-****cdef"}}'
    monkeypatch.setattr(llm_intent, "_call",
                        lambda m, k, q: (_ for _ in ()).throw(_http_error(401, body)))

    r = client.post("/api/search",
                    json={"query": "충남 분양 중", "openai_api_key": FAKE_KEY})
    assert r.status_code == 200
    assert FAKE_KEY not in r.text
    assert "USER1234567890" not in r.text
    assert "cdef" not in r.text
    assert any("폴백" in w for w in r.json()["warnings"])   # 실패 사실은 알린다


def test_success_response_never_echoes_key(monkeypatch):
    monkeypatch.setattr(llm_intent, "_call",
                        lambda m, k, q: {"sido": "충청남도", "sale_stage": ["분양중"]})
    r = client.post("/api/search",
                    json={"query": "충남 분양 중", "openai_api_key": FAKE_KEY})
    assert FAKE_KEY not in r.text
    assert r.json()["query_parsed"]["region"]["sido"] == "충청남도"


# --- 키 없을 때 기존 동작 보존 ---
def test_without_key_uses_rule_parser(monkeypatch):
    monkeypatch.setattr(config, "LLM_ENABLED", False)
    monkeypatch.setattr(llm_intent, "_call",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("키 없이 LLM을 호출하면 안 됨")))
    r = client.post("/api/search", json={"query": "충남 분양 중"})
    assert r.status_code == 200
    assert r.json()["query_parsed"]["region"]["sido"] == "충청남도"


def test_key_activates_llm_even_when_disabled(monkeypatch):
    """서버 USE_LLM이 꺼져 있어도 사용자 키가 있으면 LLM 경로를 쓴다."""
    monkeypatch.setattr(config, "LLM_ENABLED", False)
    called = {}
    monkeypatch.setattr(llm_intent, "_call",
                        lambda m, k, q: called.setdefault("hit", k) and {} or
                        {"sido": "충청남도", "sale_stage": []})
    Orchestrator().search(query="충남 분양 중", api_key=FAKE_KEY)
    assert called.get("hit") == FAKE_KEY


def test_health_advertises_byok():
    assert client.get("/api/health").json()["byok_supported"] is True
