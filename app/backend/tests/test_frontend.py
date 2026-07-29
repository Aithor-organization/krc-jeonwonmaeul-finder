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
    """기본 펼침이면 검색 흐름을 가린다 — details에 open이 없어야 한다.

    속성이 늘어도 깨지지 않게 여는 태그를 뽑아서 open 유무만 본다.
    """
    import re
    app_js = client.get("/app.js").text
    tags = re.findall(r"<details[^>]*trace-panel[^>]*>", app_js)
    assert tags, "계산 내역 패널이 details로 렌더되지 않는다"
    for tag in tags:
        assert " open" not in tag, tag


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
    """각 데이터셋의 결합 방식과 한계를 카드에서 밝힌다.

    2026-07-29 농촌마을현황 조인 이후 이 페이지가 "실시간 연동 전"이라고
    말하고 있었다 — 기능이 생기면 그걸 설명하던 문구도 같이 낡는다.
    """
    html = client.get("/data-evidence.html").text
    assert html.count('class="live-status"') >= 2
    assert "실시간 연동 전" not in html, "농촌마을현황은 이제 결합된다"
    assert "법정동코드 완전일치" in html, "결합 키를 밝혀야 한다"
    assert "파일데이터" in html, "논가뭄지도는 아직 CSV — 그 한계는 그대로 남는다"


def test_evidence_page_has_no_stale_sample_mode_claim():
    """배포본은 live인데 'sample-mode로 동작합니다'라고 단언하면 안 된다.

    푸터의 .mode-flag는 JS가 /api/health로 실시간 갱신하므로 예외.
    """
    html = client.get("/data-evidence.html").text
    body = html.replace('<span class="mode-flag">sample-mode로 동작 중</span>', "")
    assert "현재는 sample-mode" not in body
    assert "sample-mode를 유지" not in body


# --- 검색 결과 도달성 (2026-07-29) ---
# 실측: 배포본에서 마을찾기를 눌러도 5초간 스크롤이 12px에 머물렀고, 첫 카드는
# 뷰포트(1009px) 밖 1259px에 있었다. 기능은 전부 동작했지만 화면은 그대로였다.
def test_results_collapse_the_hero():
    """히어로가 880px라 결과가 항상 첫 화면 밖이다 — 검색 시 접어야 한다."""
    app_js = client.get("/app.js").text
    css = client.get("/style.css").text
    assert "function setResultsMode" in app_js
    assert "setResultsMode(true)" in app_js, "검색 시 히어로를 접어야 한다"
    assert "setResultsMode(false)" in app_js, "조건 다시 입력하면 펼쳐야 한다"
    assert "body.results-mode .hero" in css
    assert "height: auto" in css.split("body.results-mode .hero")[1][:120]


def test_scroll_has_arrival_fallback():
    """부드러운 스크롤이 진행되지 않으면 결과가 화면 밖에 남는다 — 도달을 확인한다."""
    app_js = client.get("/app.js").text
    fn = app_js.split("function scrollToElement")[1].split("\nfunction ")[0]
    assert "getBoundingClientRect" in fn, "도달 여부를 확인하지 않는다"
    assert 'behavior: "instant"' in fn, "보정 이동까지 smooth면 같은 실패를 반복한다"


def test_trace_is_reachable_from_results_heading():
    """계산 내역은 카드 아래에 있어 스크롤 전에는 존재를 모른다 — 머리에 진입점을 둔다."""
    html = client.get("/").text
    app_js = client.get("/app.js").text
    assert 'id="trace-open"' in html
    assert "el.traceOpen.addEventListener" in app_js
    assert "panel.open = true" in app_js, "버튼이 패널을 열지 않으면 이동만 하고 만다"
    # 결과가 없을 때 버튼이 남아 있으면 눌러도 아무 일도 일어나지 않는다
    assert "el.traceOpen.hidden = true" in app_js


def test_notes_are_collapsed_but_counted():
    """고지 3줄이 카드보다 먼저 나오면 첫인상이 변명이 된다 — 접되 건수는 보인다."""
    app_js = client.get("/app.js").text
    fn = app_js.split("function renderNotes")[1].split("\nfunction ")[0]
    assert '<details class="notes-panel">' in fn
    assert "messages.length" in fn.split("<summary>")[1][:80], "건수를 접힌 상태에서도 보여야 한다"


def test_unknown_metric_is_visually_demoted():
    """원천의 84%가 빈 분양율 탓에 카드 최대 글씨가 매번 '확인 불가'가 된다."""
    app_js = client.get("/app.js").text
    css = client.get("/results.css").text
    assert "function metricHtml" in app_js
    assert "is-unknown" in app_js and ".metric.is-unknown .value" in css
    demoted = css.split(".metric.is-unknown .value")[1][:200]
    base = css.split(".metric .value")[1][:200]
    import re
    size = lambda block: float(re.search(r"font-size:\s*([\d.]+)px", block).group(1))
    assert size(demoted) < size(base), "확인 불가가 실제 수치보다 작아야 한다"


# --- 결과 화면 정보 위계 (2026-07-29) ---
def test_results_headline_is_filled_with_real_numbers():
    """'조건에 맞는 전원마을'은 어떤 검색에도 똑같이 붙어 46px를 쓰고도 알려주는 게 없었다."""
    html = client.get("/").text
    app_js = client.get("/app.js").text
    assert 'id="results-lead"' in html
    assert "function renderResultsHeading" in app_js
    assert "renderResultsHeading(data.query_parsed, data.trace, results.length)" in app_js
    # 헤드라인 자리에 정적 문구가 박혀 있으면 안 된다.
    # (CTA 배너 카피 등 다른 섹션의 같은 문구는 무관하므로 h2만 본다)
    import re
    h2 = re.search(r'<h2 id="results-title"[^>]*>(.*?)</h2>', html, re.S).group(1)
    assert "조건에 맞는 전원마을" not in h2, h2


def test_headline_count_comes_from_funnel_not_card_count():
    """카드 수만 세면 '상위 3건 표시' 제한에 걸린 값이라 조건 충족 건수와 다르다."""
    app_js = client.get("/app.js").text
    fn = app_js.split("function renderResultsHeading")[1].split("\n/**")[0]
    assert "trace.funnel" in fn
    assert "funnel.length - 2" in fn, "마지막 단계는 표시 제한이므로 그 직전이 충족 건수다"


def test_empty_and_error_reset_the_headline():
    """직전 검색의 '전라남도 3곳'이 0건 화면에 남으면 정면으로 어긋난다."""
    app_js = client.get("/app.js").text
    assert "function resetResultsHeading" in app_js
    for fn_name in ("renderEmpty", "renderError"):
        fn = app_js.split("function " + fn_name)[1].split("\nfunction ")[0]
        assert "resetResultsHeading(" in fn, fn_name


def test_tied_scores_are_disclosed():
    """세 장이 전부 75%인데 01/02/03을 붙이면 없는 우열을 주장하게 된다."""
    html = client.get("/").text
    app_js = client.get("/app.js").text
    assert 'id="tie-note"' in html
    assert "function renderTieNote" in app_js
    fn = app_js.split("function renderTieNote")[1].split("\nfunction ")[0]
    assert "every((s) => s === scores[0])" in fn
    assert "순위가 아니라 표시 순서" in fn


def test_card_shows_the_score_formula():
    """점수만 있으면 근거 없는 숫자로 읽힌다 — 계산 내역은 펼쳐야 보인다."""
    app_js = client.get("/app.js").text
    css = client.get("/results.css").text
    assert "function scoreFormula" in app_js
    assert "scoreFormula(terms)" in app_js
    assert ".score-formula" in css
    # 산식은 카드와 1:1로 짝지어야 한다 (gu_id 키 충돌로 틀린 식이 표시된 전례)
    assert "scores[index] && scores[index].terms" in app_js


def test_known_metrics_come_before_unknown_ones():
    """분양율은 원천의 84%가 비어 고정 순서면 첫 칸이 매번 '확인 불가'다."""
    app_js = client.get("/app.js").text
    fn = app_js.split("function metricsHtml")[1].split("\n/**")[0]
    assert "known.concat(unknown)" in fn


def test_grade_badge_says_what_it_measures():
    """A/B/C는 근거 품질이 아니라 마을현황이 붙은 정확도다 — 라벨이 달랐다.

    주석에는 "왜 바꿨는지"가 옛 문구와 함께 적혀 있으므로 주석을 걷고 코드만 본다.
    """
    import re
    app_js = client.get("/app.js").text
    code = re.sub(r"/\*.*?\*/", "", app_js, flags=re.S)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)
    # 옛 배지는 '근거 ' + 등급문자 + '등급</span>' 로 조립됐다 ("수치 근거 확인"
    # 버튼은 정당한 문구이므로 배지 조립 패턴만 본다)
    assert "등급</span>" not in code, "등급 배지에 'N등급' 문구가 남아 있다"
    assert "esc(grade)" not in code, "배지가 여전히 등급 문자를 그대로 찍는다"
    assert "const GRADE_TEXT" in app_js
    for label in ("마을 상세 일치", "시군구 근사", "마을 상세 없음"):
        assert label in app_js, label
    assert "법정동코드" in app_js, "무엇으로 판정했는지 설명이 있어야 한다"


# --- '확인 불가'와 마을 현황의 오독 방지 (2026-07-29) ---
def test_unknown_metric_shows_why():
    """'API를 못 가져오는 거냐'는 질문이 실제로 나왔다 — 답은 '원천이 비어 있다'다.

    사유는 접힌 '데이터 한계'에도 있지만 펼치지 않으면 안 보인다.
    """
    app_js = client.get("/app.js").text
    css = client.get("/results.css").text
    assert "const UNKNOWN_REASON" in app_js
    assert "원천 미입력" in app_js
    assert "167건 중 141건이 0" in app_js, "실측 근거 숫자가 있어야 설득력이 생긴다"
    assert ".metric-reason" in css


def test_village_summary_names_its_subject():
    """지구(산북지구전원마을)와 마을(산북2리)은 다른 대상이다.

    이름 없이 숫자만 붙이면 지구의 값으로 읽혀 "빈집 0인데 왜 추천하냐"가 된다.
    """
    app_js = client.get("/app.js").text
    css = client.get("/results.css").text
    assert "주변 마을" in app_js
    assert "card.village_name" in app_js
    assert "적합도 점수에 반영하지 않습니다" in app_js
    assert ".village-note" in css


def test_card_carries_village_name():
    """마을명이 응답에 없으면 화면이 어느 마을 값인지 밝힐 수 없다."""
    got = client.post("/api/search", json={"structured": {
        "region": {"sido": "충청남도", "sigungu": None},
        "sale_stage": [], "preferences": [], "confidence": 1, "raw": "충청남도",
    }}).json()
    joined = [c for c in got["top"] if c.get("population") is not None
              or c.get("vacant_houses") is not None]
    assert joined, "마을 상세가 붙은 카드가 하나도 없으면 이 검사가 무의미하다"
    for card in joined:
        assert card.get("village_name"), f"{card['gu_name']}: 수치는 있는데 마을명이 없다"


# --- 지역 드롭다운 (2026-07-29) ---
def test_region_dropdowns_exist_and_start_hidden():
    """목록이 비었는데 드롭다운만 떠 있으면 고를 게 없는 빈 UI가 된다."""
    html = client.get("/").text
    for marker in ('id="region-filter"', 'id="sel-sido"', 'id="sel-sigungu"',
                   'id="sel-stage"', 'id="region-reset"'):
        assert marker in html, marker
    block = html.split('id="region-filter"')[1][:40]
    assert "hidden" in block, "목록 로드 전에는 숨겨야 한다"
    assert 'id="sel-sigungu" class="region-select" aria-label="시군구 선택" disabled' in html, \
        "시도를 고르기 전 시군구는 비활성이어야 한다"


def test_dropdown_only_uses_structured_path():
    """문장 없이 목록만 고른 경우엔 파싱할 문장 자체가 없다."""
    app_js = client.get("/app.js").text
    assert "function structuredFromSelects" in app_js
    assert "const structured = query ? null : structuredFromSelects();" in app_js, \
        "문장이 있으면 structured가 아니라 filters 경로여야 한다"
    assert "apiKey && !structured" in app_js, "구조화 경로에 LLM 키를 보낼 이유가 없다"


def test_dropdown_does_not_search_on_change():
    """드롭다운은 조건을 고르는 곳이지 검색을 실행하는 곳이 아니다.

    시도→시군구→단계를 좁히는 동안 세 번 검색되고, 문장을 함께 쓰려던
    사용자는 입력을 마치기도 전에 결과를 본다. 실행은 '마을 찾기' 한 곳으로.
    """
    app_js = client.get("/app.js").text
    for sel in ("selSido", "selSigungu", "selStage"):
        block = app_js.split('el.' + sel + '.addEventListener("change"')[1].split("\nel.")[0]
        assert "runSearch()" not in block, f"{sel}: 변경만으로 검색이 나간다"
    # 실행 경로는 폼 제출(마을 찾기 / Enter)만 남아야 한다
    assert 'el.form.addEventListener("submit"' in app_js


def test_text_and_dropdown_combine_instead_of_clearing():
    """둘 다 쓰면 지역·단계는 고른 값이 이기고 나머지 조건은 문장에서 읽는다."""
    app_js = client.get("/app.js").text
    assert "function selectedFilters" in app_js
    assert "payload.filters = filters" in app_js
    assert "if (hasRegionSelection()) clearRegionSelects();" not in app_js, \
        "타이핑이 드롭다운을 지우면 결합이 불가능하다"
    for sel in ("selSido", "selSigungu", "selStage"):
        block = app_js.split('el.' + sel + '.addEventListener("change"')[1].split("\nel.")[0]
        assert 'el.query.value = ""' not in block, f"{sel}: 선택이 입력창을 지운다"


def test_region_hint_explains_missing_provinces():
    """전국 17개 시도가 아니라 분양 지구가 있는 곳만 나온다 —
    밝히지 않으면 '경기도가 없는데 고장인가'로 읽힌다 (실제로 나온 질문)."""
    html = client.get("/").text
    app_js = client.get("/app.js").text
    assert 'id="region-hint"' in html
    assert "전원마을 분양 지구가 있는 " in app_js
    assert "data.시도.length" in app_js, "개수는 실제 응답에서 세야 한다"


def test_filters_override_sentence_region():
    """드롭다운 '구례군' + 문장 '조용한 곳' → 지역은 구례군, 선호는 문장에서."""
    got = client.post("/api/search", json={
        "query": "전남 조용한 마을",
        "filters": {"sido": "충청남도", "sigungu": None, "sale_stage": "분양중"},
    }).json()
    parsed = got["query_parsed"]
    assert parsed["region"]["sido"] == "충청남도", "고른 시도가 문장(전남)을 이겨야 한다"
    assert parsed["sale_stage"] == ["분양중"]
    assert any("우선 적용" in n for n in got["notes"]), "덮어썼다는 사실을 밝혀야 한다"
    for card in got["top"]:
        assert card["sido"] == "충청남도", card


def test_filters_do_not_erase_other_sentence_conditions():
    """지역만 덮어쓰고 예산·선호는 문장 해석 그대로 남아야 한다."""
    got = client.post("/api/search", json={
        "query": "예산 2억 이하 조용한 곳",
        "filters": {"sido": "충청남도", "sigungu": None, "sale_stage": None},
    }).json()
    parsed = got["query_parsed"]
    assert parsed["region"]["sido"] == "충청남도"
    assert parsed["budget_max_krw"] or parsed["preferences"], \
        "문장에서 읽은 조건이 전부 사라졌다"


def test_region_load_failure_is_silent():
    """지역 목록은 보조 수단 — 실패해도 자연어 검색은 그대로 살아야 한다."""
    app_js = client.get("/app.js").text
    fn = app_js.split("async function loadRegions")[1].split("\nasync function ")[0]
    assert "catch" in fn
    assert "el.regionFilter.hidden = false" in fn
    # 성공 경로에서만 노출 — catch 블록이 UI를 켜면 빈 드롭다운이 남는다
    assert "hidden = false" not in fn.split("catch")[1]


def test_structured_summary_does_not_claim_interpretation():
    """고른 값에 '해석 신뢰도'를 붙이면 거짓이다 — 해석한 적이 없다."""
    app_js = client.get("/app.js").text
    fn = app_js.split("function parsedSummary")[1].split("\nfunction ")[0]
    assert "isStructured" in fn
    assert "문장 해석 없음" in fn
    assert "parsedSummary(data.query_parsed, Boolean(structured))" in app_js


def test_query_input_has_length_cap():
    """서버 절단 전에 브라우저에서 먼저 막는다 (BYOK 비용 보호)."""
    import config
    html = client.get("/").text
    assert f'maxlength="{config.MAX_QUERY_CHARS}"' in html
