"""분양율 수치가 없어도 진행단계가 답을 주는 경우가 있다.

전에는 분양율이 비면 무조건 중립 0.5를 줬다. 그래서 **다 팔린 분양완료 지구가
"들어갈 자리 절반"을 받았다** — 화면에는 "분양완료 / 확인 불가"가 나란히 뜨는데
점수는 자리가 있다고 계산하는 모순.

원천 근거: 분양완료 23건 중 분양율이 기록된 6건은 예외 없이 100%.
따라서 미입력 17건도 남은 자리가 없다고 보는 것이 데이터와 맞다.
"""
import scoring
from fastapi.testclient import TestClient
from models import ParsedQuery
from main import app

client = TestClient(app)

BASE = {"지구명": "테스트지구", "시도명": "충청남도", "시군구": "예산군",
        "법정동코드": "44710310", "계획세대수": 30}


def avail_of(sale: dict) -> float:
    terms = scoring.score_breakdown(ParsedQuery(), sale, None)
    return next(t for t in terms if t["label"] == "가용성")["value"]


def basis_of(sale: dict) -> str:
    terms = scoring.score_breakdown(ParsedQuery(), sale, None)
    return next(t for t in terms if t["label"] == "가용성")["basis"]


def test_sold_out_without_rate_has_no_availability():
    """🔴 핵심 — 분양완료인데 중립 0.5를 주면 다 팔린 곳에 자리가 있다고 말하는 셈."""
    assert avail_of({**BASE, "진행단계": "분양완료", "분양율": None}) == 0.0


def test_sold_out_basis_explains_why():
    """0을 준 이유가 산식에 드러나야 한다 — 근거 없는 0은 근거 없는 0.5와 같다."""
    basis = basis_of({**BASE, "진행단계": "분양완료", "분양율": None})
    assert "분양완료" in basis and "남은 자리 없음" in basis


def test_other_stages_keep_neutral_when_rate_unknown():
    """분양중·분양예정은 수치가 없으면 정말 모른다 — 중립을 유지한다.

    실측: 분양예정 78건 중 값이 있는 13건은 70/100, 분양중 66건 중 6건은 100.
    미입력을 '덜 팔림'으로 볼 근거가 없다.
    """
    assert avail_of({**BASE, "진행단계": "분양중", "분양율": None}) == 0.5
    assert avail_of({**BASE, "진행단계": "분양예정", "분양율": None}) == 0.5


def test_explicit_rate_still_wins_over_stage():
    """수치가 있으면 그 수치가 우선 — 단계 추론은 없을 때만 쓴다."""
    assert avail_of({**BASE, "진행단계": "분양완료", "분양율": 40.0}) == 0.6


def test_sold_out_scores_below_in_progress():
    """분양완료가 분양중보다 위에 오면 순위가 뒤집힌 것이다."""
    done = scoring.score_card(ParsedQuery(), {**BASE, "진행단계": "분양완료", "분양율": None}, None)[0]
    live = scoring.score_card(ParsedQuery(), {**BASE, "진행단계": "분양중", "분양율": None}, None)[0]
    assert done < live, f"분양완료 {done} >= 분양중 {live}"


def test_card_reason_uses_the_stage(monkeypatch):
    """화면 문구도 같은 판단을 말해야 한다 — 점수만 바뀌면 사용자는 모른다."""
    app_js = client.get("/app.js").text
    assert "function unknownRateReason" in app_js
    assert "분양완료 — 남은 자리 없음" in app_js
    assert "unknownRateReason(card.sale_stage)" in app_js
