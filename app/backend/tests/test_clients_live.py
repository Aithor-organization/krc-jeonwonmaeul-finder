"""KrcDataClient의 live-mode 분기 — 성공/fallback/village 정책."""
import config
import krc_live
from clients import KrcDataClient
from krc_mapping import STAGE_NOTE

RAW = [
    {"inbpnCode": "X1", "zoneName": "가마을", "sidoNm": "전남광주통합특별시",
     "sggNm": "곡성군", "emdNm": "겸면", "legalCode": 4672025021,
     "planHscnt": 40, "progrsStep": "주택건축 단계", "bndeLttotHscntPer": 20},
    {"inbpnCode": "X2", "zoneName": "나마을", "sidoNm": "충청남도",
     "sggNm": "예산군", "emdNm": "대흥면", "legalCode": 4471031000,
     "planHscnt": 120, "progrsStep": "준비단계", "bndeLttotHscntPer": 0},
]


def test_construction_does_not_call_upstream(monkeypatch):
    """생성만으로 상류를 때리면 안 된다 — 콜드스타트에 지연이 얹히고 HTML까지 늦어진다."""
    def boom(key, **kw):
        raise AssertionError("__init__에서 fetch_sales를 호출하면 안 됨")
    monkeypatch.setattr(config, "KRC_SERVICE_KEY", "KEY")
    monkeypatch.setattr(krc_live, "fetch_sales", boom)

    c = KrcDataClient(sample_mode=False)      # 예외가 나지 않아야 통과
    assert c.live_active is False             # 아직 아무 상태도 확정되지 않음


def test_live_mode_maps_and_filters(monkeypatch):
    monkeypatch.setattr(config, "KRC_SERVICE_KEY", "KEY")
    monkeypatch.setattr(krc_live, "fetch_sales", lambda key, **kw: RAW)

    c = KrcDataClient(sample_mode=False)
    c.ensure_loaded()
    assert c.live_active is True
    assert c.sample_mode is False

    rows = c.get_sales()
    assert len(rows) == 2
    # 시도명 매핑이 적용되어 표준명으로 검색된다
    assert c.get_sales(sido="전라남도")[0]["지구명"] == "가마을"
    # 진행단계 매핑이 적용되어 서비스 어휘로 필터된다
    assert [r["지구명"] for r in c.get_sales(stages=["분양중"])] == ["가마을"]
    assert [r["지구명"] for r in c.get_sales(stages=["분양예정"])] == ["나마을"]
    assert c.get_sales(sigungu="예산군")[0]["지구명"] == "나마을"


def test_live_mode_emits_honest_notes(monkeypatch):
    """상시 안내는 notes로 — warnings(문제)와 섞이면 매 검색이 경고처럼 보인다."""
    monkeypatch.setattr(config, "KRC_SERVICE_KEY", "KEY")
    monkeypatch.setattr(krc_live, "fetch_sales", lambda key, **kw: RAW)
    c = KrcDataClient(sample_mode=False)
    c.ensure_loaded()
    assert STAGE_NOTE in c.notes         # 단계 변환 사실 고지
    assert any("스냅샷" in n for n in c.notes), "마을 상세의 기준일을 밝혀야 한다"
    assert c.warnings == []              # 정상 동작에는 경고가 없어야 한다
    assert not any("sample-mode" in n for n in c.notes)


def test_live_mode_joins_village_by_exact_code(monkeypatch):
    """live에서 법정동코드가 정확히 일치하면 인구·빈집을 붙인다.

    2026-07-29 이전에는 조인 자체를 하지 않아 인구·빈집이 항상 None이고
    신뢰도 등급이 전부 C로 고정됐다. 사전 빌드 인덱스로 해소.
    """
    monkeypatch.setattr(config, "KRC_SERVICE_KEY", "KEY")
    monkeypatch.setattr(krc_live, "fetch_sales", lambda key, **kw: RAW)
    c = KrcDataClient(sample_mode=False)
    c.ensure_loaded()
    codes = list((c._village_index.get("villages") or {}))
    assert codes, "인덱스가 비어 있으면 조인 기능이 죽는다"
    v = c.get_village(codes[0])
    assert v and v["법정동코드"] == codes[0]
    assert set(v) >= {"마을명", "인구", "빈집수"}


def test_live_mode_returns_none_for_unmatched_code(monkeypatch):
    """붙지 않으면 '확인 불가' — 읍면동만 같은 마을을 임의로 대체하지 않는다."""
    monkeypatch.setattr(config, "KRC_SERVICE_KEY", "KEY")
    monkeypatch.setattr(krc_live, "fetch_sales", lambda key, **kw: RAW)
    c = KrcDataClient(sample_mode=False)
    c.ensure_loaded()
    assert c.get_village("9999999999") is None
    assert c.get_village(None) is None


def test_live_failure_falls_back_to_sample(monkeypatch):
    def boom(key, **kw):
        raise krc_live.KrcApiError("HTTP 오류: ConnectTimeout")
    monkeypatch.setattr(config, "KRC_SERVICE_KEY", "KEY")
    monkeypatch.setattr(krc_live, "fetch_sales", boom)

    c = KrcDataClient(sample_mode=False)
    c.ensure_loaded()
    assert c.live_active is False
    assert c.sample_mode is True                 # 샘플로 내려앉음
    assert c.get_sales(), "fallback 후에도 샘플 데이터는 있어야 함"
    assert any("호출 실패" in w for w in c.warnings)   # 조용한 실패 금지
    # fallback 상태에서는 village 조인이 다시 살아난다
    assert c.get_village("44710310") is not None


def test_failure_is_retried_after_cooldown(monkeypatch):
    """한 번 실패했다고 인스턴스 수명 내내 샘플에 갇히면 안 된다."""
    monkeypatch.setattr(config, "KRC_SERVICE_KEY", "KEY")
    monkeypatch.setattr(config, "KRC_RETRY_AFTER_S", 0.0)   # 쿨다운 없이 즉시 재시도
    calls = {"n": 0}

    def flaky(key, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise krc_live.KrcApiError("HTTP 오류: ReadTimeout")
        return RAW
    monkeypatch.setattr(krc_live, "fetch_sales", flaky)

    c = KrcDataClient(sample_mode=False)
    c.ensure_loaded()
    assert c.sample_mode is True and c.warnings            # 1회차 실패 → 샘플 + 경고

    c.ensure_loaded()                                      # 2회차 → 복구
    assert c.live_active is True
    assert c.sample_mode is False
    assert c.warnings == [], "복구 후에는 이전 실패 경고가 남으면 안 된다"
    assert STAGE_NOTE in c.notes


def test_cooldown_blocks_immediate_retry(monkeypatch):
    """실패 직후 매 검색마다 느린 상류를 다시 때리지 않는다."""
    monkeypatch.setattr(config, "KRC_SERVICE_KEY", "KEY")
    monkeypatch.setattr(config, "KRC_RETRY_AFTER_S", 300.0)
    calls = {"n": 0}

    def always_fail(key, **kw):
        calls["n"] += 1
        raise krc_live.KrcApiError("HTTP 오류: ReadTimeout")
    monkeypatch.setattr(krc_live, "fetch_sales", always_fail)

    c = KrcDataClient(sample_mode=False)
    for _ in range(5):
        c.ensure_loaded()
    assert calls["n"] == 1, f"쿨다운 중에도 {calls['n']}회 호출됨"


def test_sample_mode_unchanged():
    c = KrcDataClient(sample_mode=True)
    c.ensure_loaded()
    assert c.live_active is False
    assert any("sample-mode" in n for n in c.notes)   # 안내이지 경고가 아니다
    assert c.warnings == []
    assert c.get_village("44710310") is not None


def test_no_key_never_calls_upstream(monkeypatch):
    """키가 없으면 재시도해도 의미가 없다 — 상류를 아예 부르지 않는다."""
    def boom(key, **kw):
        raise AssertionError("sample-mode에서 fetch_sales를 호출하면 안 됨")
    monkeypatch.setattr(krc_live, "fetch_sales", boom)
    c = KrcDataClient(sample_mode=True)
    for _ in range(3):
        c.ensure_loaded()
    assert c.get_sales()


def test_config_gate_follows_key_presence():
    """SAMPLE_MODE는 키 유무를 따른다 (하드코딩 제거 확인)."""
    assert config.SAMPLE_MODE == (config.KRC_SERVICE_KEY is None) or config.SAMPLE_MODE
    assert config.LIVE_KEY_PRESENT == (config.KRC_SERVICE_KEY is not None)
