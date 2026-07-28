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


def test_settings_page_is_served():
    """LLM 키 입력은 전용 설정 페이지가 담당한다."""
    response = client.get("/settings.html")
    assert response.status_code == 200
    for text in ("설정", 'id="openai-key"', 'id="key-test"', 'id="key-clear"'):
        assert text in response.text, text


def test_key_store_is_single_source():
    """저장 규칙이 한 곳에만 있어야 두 화면이 어긋나지 않는다."""
    store = client.get("/key-store.js").text
    app_js = client.get("/app.js").text
    settings_js = client.get("/settings.js").text

    assert "krc.openai_key" in store
    # 검색·설정 화면은 저장소를 쓰기만 하고 저장 키 이름을 각자 들지 않는다
    assert "krc.openai_key" not in app_js
    assert "krc.openai_key" not in settings_js
    assert "KrcKeyStore" in app_js and "KrcKeyStore" in settings_js


def test_key_store_uses_session_not_local_storage():
    """localStorage는 정적 페이지에서 남의 브라우저에 키를 무기한 남긴다.

    주석에는 "왜 안 쓰는지"가 적혀 있으므로 주석을 걷어내고 실제 사용만 본다.
    """
    import re
    store = client.get("/key-store.js").text
    code = re.sub(r"/\*.*?\*/", "", store, flags=re.S)          # 블록 주석 제거
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)           # 줄 주석 제거

    assert "sessionStorage" in code
    assert "localStorage" not in code


def test_index_shows_parser_path_and_links_to_settings():
    """어느 파서로 검색되는지 감추지 않고, 키 입력 경로를 안내한다."""
    html = client.get("/").text
    assert 'id="ai-status"' in html
    assert '/settings.html' in html
    assert 'id="openai-key"' not in html, "키 입력란은 설정 페이지에만 둔다"


def test_settings_assets_are_served():
    for path, allowed in {
        "/settings.js": ("application/javascript", "text/javascript"),
        "/key-store.js": ("application/javascript", "text/javascript"),
    }.items():
        response = client.get(path)
        assert response.status_code == 200, path
        assert any(ct in response.headers["content-type"] for ct in allowed), path


def test_settings_reachable_from_every_page():
    for path in ("/", "/how-it-works.html", "/data-evidence.html"):
        assert '/settings.html' in client.get(path).text, path


def test_no_undefined_css_classes_in_pages():
    """HTML이 CSS에 없는 클래스를 쓰면 그 요소는 스타일 없이 렌더된다.

    실제로 settings.html이 `.section-inner`(존재하지 않는 이름)를 써서
    본문이 컨테이너를 못 잡고 뷰포트 끝까지 번졌다. 오타는 조용히 깨진다.
    """
    import re
    from pathlib import Path

    frontend = Path(__file__).resolve().parents[2] / "frontend"
    css = "\n".join(p.read_text(encoding="utf-8") for p in frontend.glob("*.css"))

    for html_path in sorted(frontend.glob("*.html")):
        used = set()
        for m in re.finditer(r'class="([^"]+)"', html_path.read_text(encoding="utf-8")):
            used.update(m.group(1).split())
        missing = sorted(
            c for c in used
            if not re.search(r"[.\s,]" + re.escape(c) + r"[\s,{:>.\[]", css)
        )
        assert not missing, f"{html_path.name}: CSS 미정의 클래스 {missing}"


def test_settings_uses_shared_section_wrapper():
    """폭 제한은 .section-shell이 담당한다 — 페이지마다 다른 래퍼를 만들지 않는다."""
    html = client.get("/settings.html").text
    assert 'class="section-shell' in html
    assert "section-inner" not in html


def test_trace_panel_is_wired():
    """계산 내역 컨테이너 + 렌더 함수 + 호출이 모두 있어야 화면에 그려진다."""
    html = client.get("/").text
    app_js = client.get("/app.js").text
    assert 'id="trace"' in html
    assert "function renderTrace" in app_js
    assert "renderTrace(data.trace)" in app_js


def test_trace_is_collapsed_by_default():
    """기본 펼침이면 검색 흐름을 가린다 — details에 open이 없어야 한다."""
    app_js = client.get("/app.js").text
    assert '<details class="trace-panel">' in app_js
    assert '<details class="trace-panel" open' not in app_js


def test_trace_cleared_on_error():
    """실패 화면에 직전 검색의 계산 내역이 남으면 그 자체가 거짓 표시가 된다."""
    app_js = client.get("/app.js").text
    error_fn = app_js.split("function renderError")[1].split("function ")[0]
    assert "renderTrace(null)" in error_fn


# --- 랜딩 주장 ↔ 실제 동작 정합 (2026-07-28) ---
def test_hero_claims_hold_in_live_mode():
    """랜딩 숫자가 프로덕션과 다르면 그 격차가 가장 먼저 눈에 띈다.

    실제로 "3종 데이터 연계"(1종만 live)와 "A–D 등급"(전부 C)이 어긋나 있었다.
    """
    html = client.get("/").text
    assert "3종" not in html.split("hero-proof")[1][:400], "1종만 연동인데 3종이라 쓰면 안 된다"
    assert "A–D" not in html.split("hero-proof")[1][:400], "live에서 전부 C인데 A–D라 쓰면 안 된다"
    assert "167곳" in html, "실측 가능한 숫자로 대체돼야 한다"


def test_hero_number_matches_actual_dataset_size():
    """'167곳'이 실제 수록 건수와 일치해야 한다 — 숫자가 하드코딩이라 드리프트가 쉽다."""
    import re
    from clients import KrcDataClient
    html = client.get("/").text
    m = re.search(r"<strong>(\d+)곳</strong>", html)
    assert m, "히어로에 수록 건수가 없다"
    claimed = int(m.group(1))
    c = KrcDataClient(sample_mode=True)
    c.ensure_loaded()
    # 샘플 모드에서는 건수가 다르므로 상한만 확인 — live 실측값(167)을 넘겨 적으면 안 된다
    assert claimed == 167, f"히어로 표기 {claimed} != live 실측 167 (원천 totalCount)"


def test_evidence_page_discloses_live_status_per_dataset():
    """설계와 현재 동작이 다르면 데이터셋 카드에서 그 사실을 밝힌다."""
    html = client.get("/data-evidence.html").text
    assert html.count('class="live-status"') >= 2, "미연동 2종의 상태 고지가 필요"
    assert "실시간 연동 전" in html
    assert "파일데이터" in html


def test_query_input_has_length_cap():
    """서버 절단 전에 브라우저에서 먼저 막는다 (BYOK 비용 보호)."""
    import config
    html = client.get("/").text
    assert f'maxlength="{config.MAX_QUERY_CHARS}"' in html
