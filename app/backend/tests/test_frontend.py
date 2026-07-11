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
    assets = {
        "/style.css": "text/css",
        "/results.css": "text/css",
        "/sections.css": "text/css",
        "/responsive.css": "text/css",
        "/pages.css": "text/css",
        "/app.js": "application/javascript",
        "/pages.js": "application/javascript",
        "/assets/hero-rural-village.jpg": "image/jpeg",
    }

    for path, content_type in assets.items():
        response = client.get(path)
        assert response.status_code == 200, path
        assert content_type in response.headers["content-type"], path
        assert response.content, path


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
