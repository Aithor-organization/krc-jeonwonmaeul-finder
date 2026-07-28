"""정적 랜딩페이지와 핵심 자산의 서빙 계약."""

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_landing_page_exposes_search_first():
    response = client.get("/")

    assert response.status_code == 200
    assert "전원마을 파인더" in response.text
    assert 'id="search-form"' in response.text
    assert 'id="view-results"' in response.text
    assert 'id="modal"' in response.text


def test_landing_assets_are_served_locally():
    # 값은 허용되는 content-type 후보들 (starlette 버전별 .js MIME 상이:
    # 구버전 application/javascript, 신버전 text/javascript — 둘 다 정상)
    assets = {
        "/style.css": ("text/css",),
        "/results.css": ("text/css",),
        "/sections.css": ("text/css",),
        "/responsive.css": ("text/css",),
        "/pages.css": ("text/css",),
        "/app.js": ("application/javascript", "text/javascript"),
        "/pages.js": ("application/javascript", "text/javascript"),
        "/assets/hero-rural-village.jpg": ("image/jpeg",),
    }

    for path, allowed_types in assets.items():
        response = client.get(path)
        assert response.status_code == 200, path
        actual = response.headers["content-type"]
        assert any(ct in actual for ct in allowed_types), (path, actual)
        assert response.content, path


def test_mode_flag_is_synced_by_script_not_hardcoded():
    """푸터 모드 표시가 JS로 갱신되는지 — 하드코딩만 있으면 실제 모드와 어긋난다."""
    app_js = client.get("/app.js").text
    pages_js = client.get("/pages.js").text
    assert "mode-flag" in app_js, "index는 app.js가 푸터를 갱신해야 함"
    assert "mode-flag" in pages_js, "하위 페이지는 pages.js가 갱신해야 함"
    # 두 스크립트 모두 health 응답을 근거로 판단해야 한다
    assert "/api/health" in app_js and "/api/health" in pages_js


def test_village_summary_is_conditional():
    """인구·빈집이 모두 없으면 마을현황 줄을 그리지 않는다."""
    app_js = client.get("/app.js").text
    assert "card.population != null || card.vacant_houses != null" in app_js


def test_notes_container_exists():
    html = client.get("/").text
    assert 'id="notes"' in html


def test_information_pages_are_served():
    pages = {
        "/how-it-works.html": ("작동 방식", "요청 처리"),
        "/data-evidence.html": ("데이터 근거", "세 개의 공공데이터"),
    }

    for path, expected_copy in pages.items():
        response = client.get(path)
        assert response.status_code == 200, path
        for text in expected_copy:
            assert text in response.text, (path, text)
