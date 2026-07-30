"""빈집은 세 상태다 — 있음 / 없음 / 모름.

사용자 질문: "여기 빈집이 있는 곳인지 확실한 거야?" · "동박골은 왜 아무것도
안 적혀있어?"

🔴 둘 다 직전 turn에 내가 만든 회귀다.
  · "빈집 0은 변별력이 없다"며 **화면에서 숨겼다**. 점수에서 빼는 판단은
    맞았지만(127곳 중 65곳이 0이라 순위를 못 가른다) 표시까지 지운 건 틀렸다 —
    조사돼서 0인 곳(65)과 조사가 안 된 곳(28)이 똑같이 침묵했다.
  · 마을이 안 붙는 지구(167곳 중 16곳)는 카드 본문이 통째로 비었다.
    배지에 "마을 상세 없음"이 있지만 툴팁이라 안 읽힌다.

모르는 것을 모른다고 적는 게 이 서비스의 전부인데, 그 반대를 했다.
"""
import json
from pathlib import Path

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
INDEX = Path(__file__).resolve().parents[1] / "data" / "village_index.json"


def app_js() -> str:
    return client.get("/app.js").text


def test_three_vacant_states_all_exist_in_the_data():
    """세 상태가 실제로 다 존재해야 구분할 이유가 있다.

    실측(127곳): 1호 이상 34 · 조사된 0이 65 · 미조사 28.
    """
    villages = list(json.loads(INDEX.read_text(encoding="utf-8"))["villages"].values())
    has = sum(1 for v in villages if v["빈집수"])
    zero = sum(1 for v in villages if v["빈집수"] == 0)
    unknown = sum(1 for v in villages if v["빈집수"] is None)
    assert has and zero and unknown, (has, zero, unknown)
    # 셋으로 남김없이 갈리는지 — 새는 값이 있으면 화면에서 조용히 사라진다
    assert has + zero + unknown == len(villages)


def test_zero_and_unknown_are_worded_differently():
    """🔴 핵심 — 조사된 0과 미조사가 같은 문구면 구분되지 않는다."""
    js = app_js()
    assert '"빈집 없음"' in js, "조사돼서 0인 곳을 침묵시키면 안 된다"
    assert "빈집 미조사" in js, "조사 안 된 곳도 그렇다고 말해야 한다"
    assert "card.vacant_houses === 0" in js, "0과 null을 구분하는 분기가 있어야 한다"


def test_vacant_count_is_still_shown_when_present():
    """1호 이상은 그대로 숫자로 — 빈집 20호인 마을이 2곳 있다."""
    js = app_js()
    assert '"빈집 " + esc(formatNumber(card.vacant_houses, "호"))' in js


def test_unknown_state_is_visually_distinct():
    css = client.get("/results.css").text
    assert ".stat-unknown" in css, "미조사가 아는 값과 같은 스타일이면 구분이 안 된다"


# ── 마을이 안 붙은 카드 ──

def test_unjoined_card_explains_itself():
    """비어 있다는 사실보다 왜 비었는지가 정보다."""
    js = app_js()
    assert "village-missing" in js
    assert "마을 현황을 붙이지 못했습니다" in js
    assert "167곳 중 16곳" in js, "얼마나 흔한 일인지 함께 알려야 한다"


def test_unjoined_card_states_we_did_not_guess():
    """읍면동만 맞춰 남의 마을 수치를 붙이지 않았다는 점이 이 서비스의 선택이다."""
    js = app_js()
    assert "읍면동만 맞춰 다른 마을 수치를 가져다 붙이지는 않습니다" in js


def test_published_unjoined_count_matches_the_index():
    """화면에 적은 16곳이 실제 인덱스와 어긋나면 그 문장이 거짓이 된다."""
    meta = json.loads(INDEX.read_text(encoding="utf-8"))
    unjoined = meta["sale_districts"] - meta["matched_districts"]
    assert unjoined == 16, f"실측 {unjoined}곳 — app.js 문구를 함께 고쳐야 한다"
    assert meta["sale_districts"] == 167


def test_missing_block_replaces_the_silent_empty_return():
    """빈 문자열을 반환하던 자리에 안내가 들어갔는지 (조용한 공백 금지)."""
    js = app_js()
    fn = js.split("function villageBlockHtml")[1].split("\n/**")[0]
    guard = fn.split("!resourceDetail.length")[1][:400]
    assert 'return ""' not in guard, "아무것도 없을 때 조용히 빈 문자열을 돌려주면 안 된다"
