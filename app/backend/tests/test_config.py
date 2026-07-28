"""config.drought_stage_from_ratio 경계값 테스트 (논가뭄지도 평년대비 임계)."""
import config


def test_drought_stage_none():
    assert config.drought_stage_from_ratio(None) == "확인 불가"


def test_drought_stage_boundaries():
    # 임계: <=40 심각, <=50 경계, <=60 주의, <=70 관심, else 정상
    assert config.drought_stage_from_ratio(30) == "심각"
    assert config.drought_stage_from_ratio(40) == "심각"
    assert config.drought_stage_from_ratio(45) == "경계"
    assert config.drought_stage_from_ratio(50) == "경계"
    assert config.drought_stage_from_ratio(55) == "주의"
    assert config.drought_stage_from_ratio(60) == "주의"
    assert config.drought_stage_from_ratio(65) == "관심"
    assert config.drought_stage_from_ratio(70) == "관심"
    assert config.drought_stage_from_ratio(80) == "정상"
    assert config.drought_stage_from_ratio(100) == "정상"


def test_live_key_present_flag_matches_key():
    # LIVE_KEY_PRESENT는 KRC_SERVICE_KEY 유무를 반영
    assert config.LIVE_KEY_PRESENT == (config.KRC_SERVICE_KEY is not None)


def test_dataset_ids_are_fixed():
    # 기획서 P0 필수 3종 + 선택 1종 데이터셋 ID 고정 확인
    assert config.API_SALE == "15104395"
    assert config.API_VILLAGE == "15104291"
    assert config.API_DROUGHT == "15117185"
    assert config.API_RESERVOIR == "15099919"
    assert "apis.data.go.kr" in config.ALLOWLIST_HOSTS
