"""AC5 — 30문항 자연어 파싱 정확도 ≥ 80% (필드 단위)."""
import intent

CASES = [
    {"q": "충남 예산 2억 분양 진행 중인 조용한 마을", "sido": "충청남도", "budget": 200_000_000, "stage": "분양중"},
    {"q": "전남 곡성 분양 중", "sido": "전라남도", "stage": "분양중"},
    {"q": "강원도 홍천 스마트팜", "sido": "강원특별자치도", "pref": "스마트팜"},
    {"q": "경북 예산 미정 분양 예정", "sido": "경상북도", "stage": "분양예정"},
    {"q": "충청남도 홍성 1억5천", "sido": "충청남도", "budget": 150_000_000},
    {"q": "전북 5000만원 빈집 적은 곳", "sido": "전라북도", "budget": 50_000_000, "pref": "빈집적음"},
    {"q": "경기 3억 교통 좋은 전원마을", "sido": "경기도", "budget": 300_000_000, "pref": "교통편의"},
    {"q": "제주 조용한 마을", "sido": "제주특별자치도", "pref": "조용함"},
    {"q": "경남 청년 창업농", "sido": "경상남도", "pref": "청년창업"},
    {"q": "충북 분양 완료된 지구", "sido": "충청북도", "stage": "분양완료"},
    {"q": "대전 근처 분양 중", "sido": "대전광역시", "stage": "분양중"},
    {"q": "울산 2억 조용한", "sido": "울산광역시", "budget": 200_000_000, "pref": "조용함"},
    {"q": "세종 스마트팜 관심", "sido": "세종특별자치시", "pref": "스마트팜"},
    {"q": "강원 4억 분양 예정", "sido": "강원특별자치도", "budget": 400_000_000, "stage": "분양예정"},
    {"q": "전남 구례 과수 재배", "sido": "전라남도", "pref": "과수재배"},
    {"q": "충남 축산 가능한 곳", "sido": "충청남도", "pref": "축산"},
    {"q": "경북 안동 1억", "sido": "경상북도", "budget": 100_000_000},
    {"q": "전북 교통 접근성 좋은", "sido": "전라북도", "pref": "교통편의"},
    {"q": "경기 빈집 적고 조용한", "sido": "경기도", "pref": "빈집적음"},
    {"q": "충남 예산 분양 진행 중", "sido": "충청남도", "stage": "분양중"},
    {"q": "부산 근교 2억5천", "sido": "부산광역시", "budget": 250_000_000},
    {"q": "강원 홍천 3억 분양 중", "sido": "강원특별자치도", "budget": 300_000_000, "stage": "분양중"},
    {"q": "전남 6000만원", "sido": "전라남도", "budget": 60_000_000},
    {"q": "충북 청주 조용", "sido": "충청북도", "pref": "조용함"},
    {"q": "경남 진주 분양 예정", "sido": "경상남도", "stage": "분양예정"},
    {"q": "인천 강화 한적한 곳", "sido": "인천광역시", "pref": "조용함"},
    {"q": "제주 서귀포 2억", "sido": "제주특별자치도", "budget": 200_000_000},
    {"q": "경북 상주 과수", "sido": "경상북도", "pref": "과수재배"},
    {"q": "충남 논산 분양 완료", "sido": "충청남도", "stage": "분양완료"},
    {"q": "전북 남원 청년농 스마트팜", "sido": "전라북도", "pref": "청년창업"},
]


def test_parse_accuracy_ac5():
    total = 0
    correct = 0
    for c in CASES:
        p = intent.parse(c["q"])
        if "sido" in c:
            total += 1
            correct += int(p.region.sido == c["sido"])
        if "budget" in c:
            total += 1
            correct += int(p.budget_max_krw == c["budget"])
        if "stage" in c:
            total += 1
            correct += int(c["stage"] in p.sale_stage)
        if "pref" in c:
            total += 1
            correct += int(c["pref"] in p.preferences)
    acc = correct / total
    assert acc >= 0.80, f"파싱 정확도 {acc:.2%} < 80% ({correct}/{total})"
