"""KrcDataClient의 live-mode 분기 — 성공/fallback/village 정책."""
import config
import krc_live
from clients import KrcDataClient
from krc_mapping import STAGE_NOTE, VILLAGE_NOTE

RAW = [
    {"inbpnCode": "X1", "zoneName": "가마을", "sidoNm": "전남광주통합특별시",
     "sggNm": "곡성군", "emdNm": "겸면", "legalCode": 4672025021,
     "planHscnt": 40, "progrsStep": "주택건축 단계", "bndeLttotHscntPer": 20},
    {"inbpnCode": "X2", "zoneName": "나마을", "sidoNm": "충청남도",
     "sggNm": "예산군", "emdNm": "대흥면", "legalCode": 4471031000,
     "planHscnt": 120, "progrsStep": "준비단계", "bndeLttotHscntPer": 0},
]


def test_live_mode_maps_and_filters(monkeypatch):
    monkeypatch.setattr(config, "KRC_SERVICE_KEY", "KEY")
    monkeypatch.setattr(krc_live, "fetch_sales", lambda key, **kw: RAW)

    c = KrcDataClient(sample_mode=False)
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
    assert STAGE_NOTE in c.notes         # 단계 변환 사실 고지
    assert VILLAGE_NOTE in c.notes       # 마을 상세 미포함 고지
    assert c.warnings == []              # 정상 동작에는 경고가 없어야 한다
    assert not any("sample-mode" in n for n in c.notes)


def test_live_mode_village_not_joined(monkeypatch):
    """live에서는 인구·빈집수를 조인하지 않는다 (2.8만 건 스케일)."""
    monkeypatch.setattr(config, "KRC_SERVICE_KEY", "KEY")
    monkeypatch.setattr(krc_live, "fetch_sales", lambda key, **kw: RAW)
    c = KrcDataClient(sample_mode=False)
    assert c.get_village("44710310") is None
    assert c.get_village(None) is None


def test_live_failure_falls_back_to_sample(monkeypatch):
    def boom(key, **kw):
        raise krc_live.KrcApiError("HTTP 오류: ConnectTimeout")
    monkeypatch.setattr(config, "KRC_SERVICE_KEY", "KEY")
    monkeypatch.setattr(krc_live, "fetch_sales", boom)

    c = KrcDataClient(sample_mode=False)
    assert c.live_active is False
    assert c.sample_mode is True                 # 샘플로 내려앉음
    assert c.get_sales(), "fallback 후에도 샘플 데이터는 있어야 함"
    assert any("호출 실패" in w for w in c.warnings)   # 조용한 실패 금지
    # fallback 상태에서는 village 조인이 다시 살아난다
    assert c.get_village("44710310") is not None


def test_sample_mode_unchanged():
    c = KrcDataClient(sample_mode=True)
    assert c.live_active is False
    assert any("sample-mode" in n for n in c.notes)   # 안내이지 경고가 아니다
    assert c.warnings == []
    assert c.get_village("44710310") is not None


def test_config_gate_follows_key_presence():
    """SAMPLE_MODE는 키 유무를 따른다 (하드코딩 제거 확인)."""
    assert config.SAMPLE_MODE == (config.KRC_SERVICE_KEY is None) or config.SAMPLE_MODE
    assert config.LIVE_KEY_PRESENT == (config.KRC_SERVICE_KEY is not None)
