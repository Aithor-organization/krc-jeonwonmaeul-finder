from clients import KrcDataClient


def test_sample_mode_notes():
    c = KrcDataClient(sample_mode=True)
    c.ensure_loaded()          # 상태는 지연 확정 (콜드스타트에 상류 지연을 얹지 않으려고)
    assert c.sample_mode
    assert any("sample-mode" in n for n in c.notes)


def test_get_sales_filter():
    c = KrcDataClient(sample_mode=True)
    chungnam = c.get_sales(sido="충청남도")
    assert len(chungnam) == 3
    active = c.get_sales(sido="충청남도", stages=["분양중"])
    assert all(r["진행단계"] == "분양중" for r in active)
    assert len(active) == 2  # 대흥, 갈산 (신양은 분양완료)


def test_get_village_and_drought():
    c = KrcDataClient(sample_mode=True)
    v = c.get_village("44710310")
    assert v and v["마을명"] == "대흥마을"
    d = c.get_drought("예산군")
    assert d and d["가뭄단계"] == "주의"
    assert c.get_village("nonexistent") is None
    assert c.get_drought(None) is None
