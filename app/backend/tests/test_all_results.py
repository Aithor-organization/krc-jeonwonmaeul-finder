"""상위 3곳 뒤에 가려진 나머지를 볼 수 있어야 한다.

사용자 지적: "top3만 보여줄 게 아니라 나머지 충족되는 것들도 보여지는
페이지를 따로 더보기 버튼을 만들어서 연결해야 될 것 같고"

맞다. 화면에는 "조건 충족 56곳 · 상위 3곳 표시"라고 적어 놓고 나머지 53곳을
볼 방법이 없었다 — 계산을 공개한다면서 결과의 대부분을 감춘 셈이다.

그리고 고치는 과정에서 **top_n이 요청 스키마에 없어 조용히 무시되고 있었다**는
것이 드러났다. orchestrator는 top_n을 받는데 SearchRequest에 필드가 없어
Pydantic이 버렸고, 무엇을 넣든 항상 3건만 돌아왔다.
"""
import re

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# 샘플 6곳 중 4곳이 분양중이라, 기본 3건 상한이 실제로 잘리는 조건이다
WIDE = "분양 중인 마을"


def test_top_n_is_actually_honoured():
    """🔴 이 필드가 없어서 요청의 top_n이 조용히 버려지고 있었다."""
    one = client.post("/api/search", json={"query": WIDE, "top_n": 1}).json()
    many = client.post("/api/search", json={"query": WIDE, "top_n": 20}).json()
    assert len(one["top"]) == 1
    assert len(many["top"]) > 3, f"top_n=20인데 {len(many['top'])}건"


def test_top_n_defaults_to_three():
    """홈 화면 계약은 그대로 — 안 넣으면 3건에서 잘린다."""
    res = client.post("/api/search", json={"query": WIDE}).json()
    assert len(res["top"]) == 3, "기본값이 바뀌면 홈 화면 레이아웃 전제가 깨진다"


def test_top_n_is_bounded():
    """상한 167 = 원천 지구 전체. 그 이상을 요구하면 거절한다."""
    assert client.post("/api/search", json={"query": WIDE, "top_n": 500}).status_code == 422
    assert client.post("/api/search", json={"query": WIDE, "top_n": 0}).status_code == 422


def test_all_results_page_is_served():
    res = client.get("/all-results.html")
    assert res.status_code == 200
    assert "조건을 충족한" in res.text
    assert client.get("/all-results.js").status_code == 200


def test_all_results_asks_for_everything():
    js = client.get("/all-results.js").text
    assert "top_n: 167" in js, "전체 목록인데 상한을 안 걸면 3건만 온다"


def test_all_results_reads_condition_from_url():
    """새로고침·공유가 되려면 조건이 주소에 실려야 한다."""
    js = client.get("/all-results.js").text
    assert "URLSearchParams(location.search)" in js
    for key in ('"q"', '"sido"', '"sigungu"', '"stage"'):
        assert key in js, key


def test_all_results_shows_how_it_narrowed():
    """목록만 주고 과정을 감추면 홈과 같은 문제가 된다."""
    js = client.get("/all-results.js").text
    assert "funnel" in js and "이 목록이 나온 과정" in js


def test_home_links_to_the_full_list_when_hiding_some():
    home = client.get("/").text
    assert 'id="see-all"' in home
    js = client.get("/app.js").text
    assert "/all-results.html?" in js
    assert "allResultsQuery" in js


def test_see_all_is_hidden_when_nothing_is_hidden():
    """전부 보여 준 경우까지 '전체 보기'를 띄우면 거짓 신호다."""
    js = client.get("/app.js").text
    fn = js.split("function renderResultsHeading")[1].split("\n/**")[0]
    assert "matched > shown" in fn
    assert "el.seeAll.hidden = !hidden" in fn
