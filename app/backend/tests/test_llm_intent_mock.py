"""llm_intent 경로 커버리지 — 실제 OpenAI 호출 없이 mock으로 검증.

load_key(env/file/없음), _call 성공, _to_parsed, parse 성공/HTTPError폴백/일반예외폴백.
"""
import urllib.error

import pytest

import config
import llm_intent


# --- load_key ---
def test_load_key_from_env(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_KEY_ENV", "sk-env-key")
    assert llm_intent.load_key() == "sk-env-key"


def test_load_key_from_file(monkeypatch, tmp_path):
    keyfile = tmp_path / "키저장.md"
    keyfile.write_text("메모\nOpenAI API Key: sk-file-key\n다른줄\n", encoding="utf-8")
    monkeypatch.setattr(config, "OPENAI_KEY_ENV", None)
    monkeypatch.setattr(config, "OPENAI_KEY_FILE", str(keyfile))
    assert llm_intent.load_key() == "sk-file-key"


def test_load_key_missing_file(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_KEY_ENV", None)
    monkeypatch.setattr(config, "OPENAI_KEY_FILE", "/no/such/file.md")
    assert llm_intent.load_key() is None


def test_load_key_file_without_match(monkeypatch, tmp_path):
    keyfile = tmp_path / "empty.md"
    keyfile.write_text("아무 키도 없음\n", encoding="utf-8")
    monkeypatch.setattr(config, "OPENAI_KEY_ENV", None)
    monkeypatch.setattr(config, "OPENAI_KEY_FILE", str(keyfile))
    assert llm_intent.load_key() is None


# --- _to_parsed ---
def test_to_parsed_full():
    raw = {
        "sido": "충청남도", "sigungu": "예산군",
        "budget_max_krw": 200000000, "sale_stage": ["분양중"],
        "household_min": 30, "preferences": ["조용함", "교통편의"],
    }
    parsed = llm_intent._to_parsed(raw, "충남 예산 2억 분양중")
    assert parsed.region.sido == "충청남도"
    assert parsed.region.sigungu == "예산군"
    assert parsed.budget_max_krw == 200000000
    assert parsed.sale_stage == ["분양중"]
    assert parsed.household_min == 30
    assert parsed.preferences == ["조용함", "교통편의"]
    assert 0.0 < parsed.confidence <= 1.0


def test_to_parsed_handles_nulls_and_bad_types():
    raw = {
        "sido": None, "sigungu": None,
        "budget_max_krw": "not-a-number", "sale_stage": [1, "분양중"],
        "household_min": None, "preferences": None,
    }
    parsed = llm_intent._to_parsed(raw, "질의")
    assert parsed.region.sido is None
    assert parsed.budget_max_krw is None      # 잘못된 타입은 무시
    assert parsed.sale_stage == ["분양중"]     # 문자열만 통과
    assert parsed.preferences == []


# --- parse (mock _call) ---
def test_parse_success(monkeypatch):
    monkeypatch.setattr(llm_intent, "load_key", lambda: "sk-fake")
    monkeypatch.setattr(
        llm_intent, "_call",
        lambda model, key, query: {"sido": "전라남도", "sigungu": "곡성군",
                                    "budget_max_krw": None, "sale_stage": ["분양예정"],
                                    "household_min": None, "preferences": []},
    )
    parsed, meta = llm_intent.parse("전남 곡성군 분양 예정")
    assert meta["fallback"] is False
    assert meta["model"] in (config.LLM_MODEL_SIMPLE, config.LLM_MODEL_MEDIUM,
                             config.LLM_MODEL_COMPLEX)
    assert parsed.region.sido == "전라남도"
    assert parsed.sale_stage == ["분양예정"]


def test_parse_http_error_falls_back(monkeypatch):
    def boom(model, key, query):
        raise urllib.error.HTTPError("http://x", 429, "rate limit", {},
                                     _make_fp(b"too many requests"))
    monkeypatch.setattr(llm_intent, "load_key", lambda: "sk-fake")
    monkeypatch.setattr(llm_intent, "_call", boom)
    parsed, meta = llm_intent.parse("충남 예산 2억 분양 중")
    assert meta["fallback"] is True
    assert "http_429" in meta["error"]
    assert parsed.region.sido == "충청남도"    # 결정론 폴백 동작


def test_parse_generic_error_falls_back(monkeypatch):
    def boom(model, key, query):
        raise ValueError("json broke")
    monkeypatch.setattr(llm_intent, "load_key", lambda: "sk-fake")
    monkeypatch.setattr(llm_intent, "_call", boom)
    parsed, meta = llm_intent.parse("충남 예산 2억 분양 중")
    assert meta["fallback"] is True
    assert "ValueError" in meta["error"]
    assert parsed.region.sido == "충청남도"


def test_parse_no_key_falls_back(monkeypatch):
    monkeypatch.setattr(llm_intent, "load_key", lambda: None)
    parsed, meta = llm_intent.parse("충남 예산 2억 분양 중")
    assert meta["fallback"] is True
    assert meta["error"] == "no_api_key"


def _make_fp(data: bytes):
    import io
    return io.BytesIO(data)
