"""LLM 모델 라우팅 테스트. route_model은 항상, 라이브 호출은 USE_LLM+키 있을 때만."""
import pytest

import config
import llm_intent


def test_route_model_tiers():
    assert llm_intent.route_model("충남")[0] == "simple"
    assert llm_intent.route_model("충남")[1] == "gpt-5.4-nano"
    assert llm_intent.route_model("전남 곡성군 3억 분양 예정 지역")[0] == "medium"
    assert llm_intent.route_model("전남 곡성군 3억 분양 예정 지역")[1] == "gpt-5.4-mini"
    t, m = llm_intent.route_model("충남 예산 2억 분양 중 조용하고 교통 좋은 청년 스마트팜 마을")
    assert t == "complex" and m == "gpt-5.6-luna"


def test_llm_fallback_without_key(monkeypatch):
    """키 없으면 결정론 파서로 폴백."""
    monkeypatch.setattr(config, "OPENAI_KEY_ENV", None)
    monkeypatch.setattr(config, "OPENAI_KEY_FILE", "/nonexistent/path.md")
    parsed, meta = llm_intent.parse("충남 예산 2억 분양 중")
    assert meta["fallback"] is True
    assert parsed.region.sido == "충청남도"  # 결정론 파서가 처리


@pytest.mark.skipif(
    not (config.LLM_ENABLED and llm_intent.load_key()),
    reason="USE_LLM 미설정 또는 키 없음 — 라이브 LLM 호출 스킵",
)
def test_live_parse_real_api():
    parsed, meta = llm_intent.parse("충남 예산 2억 분양 진행 중")
    assert meta["fallback"] is False
    assert meta["model"] in (config.LLM_MODEL_SIMPLE, config.LLM_MODEL_MEDIUM, config.LLM_MODEL_COMPLEX)
    assert parsed.region.sido == "충청남도"
    assert parsed.budget_max_krw == 200_000_000
