"""농촌마을현황 조인 인덱스 — 커밋된 데이터 자체의 무결성.

인덱스는 사전 빌드 산출물이라 코드 리뷰로 걸러지지 않는다. 값이 조용히
틀어지면 화면 수치가 그대로 틀리므로 데이터 자체를 검사한다.
"""
import json

import config
from clients import KrcDataClient

INDEX_PATH = config.BASE_DIR / "data" / "village_index.json"


def load():
    with open(INDEX_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_index_exists_and_has_provenance():
    """기준일 없는 스냅샷은 근거가 아니다."""
    p = load()
    assert p["villages"], "인덱스가 비면 조인 기능이 죽는다"
    assert p["generated_at"], "생성 시각이 없으면 언제 기준인지 알 수 없다"
    assert p["source_api"] == "15104291"
    assert p["join_key"].startswith("법정동코드")


def test_district_and_village_counts_are_distinct():
    """🔴 지구 수와 마을 수를 섞으면 고지 문구가 틀린다.

    실제로 '127/167개 지구'라고 쓸 뻔했다 — 127은 마을 수(코드 중복 제거),
    167은 지구 수다. 여러 지구가 한 법정동코드를 공유한다.
    """
    p = load()
    assert p["matched_villages"] == len(p["villages"])
    assert p["matched_districts"] >= p["matched_villages"], \
        "지구는 마을보다 많거나 같다 (코드 공유)"
    assert p["matched_districts"] <= p["sale_districts"]


def test_population_zero_is_stored_as_unknown():
    """인구 0은 미입력이다 — 주택 200채인 마을에 사람이 0명일 수 없다."""
    for v in load()["villages"].values():
        assert v["인구"] is None or v["인구"] > 0, f"{v['마을명']}: 인구 0이 값으로 저장됨"


def test_vacant_houses_kept_only_when_village_has_data():
    """빈집 0은 '없다'일 수 있지만, 마을 자체가 비어 있으면 그 0도 미입력이다."""
    for v in load()["villages"].values():
        if v["인구"] is None and v["총주택수"] is None:
            assert v["빈집수"] is None, f"{v['마을명']}: 빈 레코드인데 빈집수가 값으로 남음"


def test_index_has_no_free_text_description():
    """villDescription은 '자원'이 아니라 마을 연혁·지리 서술이다.

    선호 매칭(조용함/교통편의)에 넣으면 노이즈만 는다. 조용함은 인구로,
    빈집적음은 빈집수로 판정하고 나머지는 매칭하지 않는다(지어내지 않는다).
    """
    p = load()
    for v in p["villages"].values():
        assert "자원" not in v and "villDescription" not in v
    assert len(json.dumps(p, ensure_ascii=False).encode()) < 200_000, \
        "인덱스가 커지면 서버리스 번들에 부담"


def test_every_entry_has_consistent_key():
    for code, v in load()["villages"].items():
        assert v["법정동코드"] == code
        assert v["마을명"], f"{code}: 마을명 없음"


def test_sample_mode_does_not_use_the_index():
    """샘플 모드는 기존 샘플 데이터를 그대로 쓴다 (오프라인 동작 보존)."""
    c = KrcDataClient(sample_mode=True)
    c.ensure_loaded()
    v = c.get_village("44710310")
    assert v and v["마을명"] == "대흥마을"


def test_missing_index_degrades_gracefully(monkeypatch):
    """인덱스 파일이 없어도 서비스는 살아야 한다 — 조인만 빠진다."""
    import clients
    monkeypatch.setattr(clients, "_load_village_index", lambda: {})
    c = clients.KrcDataClient(sample_mode=True)
    c.ensure_loaded()
    assert c.get_sales(), "인덱스가 없다고 검색이 죽으면 안 된다"
