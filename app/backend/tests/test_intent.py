import intent


def test_region_sido():
    assert intent.parse("충남 예산으로 가고 싶어요").region.sido == "충청남도"
    assert intent.parse("전남 곡성").region.sido == "전라남도"
    assert intent.parse("강원도 홍천").region.sido == "강원특별자치도"


def test_budget():
    assert intent.parse("예산 2억").budget_max_krw == 200_000_000
    assert intent.parse("1억5천").budget_max_krw == 150_000_000
    assert intent.parse("5000만원").budget_max_krw == 50_000_000
    assert intent.parse("예산 미정").budget_max_krw is None


def test_stage():
    assert "분양중" in intent.parse("분양 진행 중인 곳").sale_stage
    assert "분양예정" in intent.parse("분양 예정 지구").sale_stage
    assert "분양완료" in intent.parse("분양 완료된 곳").sale_stage


def test_preferences():
    p = intent.parse("조용하고 빈집 적은 마을")
    assert "조용함" in p.preferences
    assert "빈집적음" in p.preferences


def test_full_query_confidence():
    p = intent.parse("충남, 예산 2억, 분양 진행 중인 조용한 전원마을")
    assert p.region.sido == "충청남도"
    assert p.budget_max_krw == 200_000_000
    assert "분양중" in p.sale_stage
    assert "조용함" in p.preferences
    assert p.confidence >= 0.6
