"use strict";

const $ = (selector, root = document) => root.querySelector(selector);

const el = {
  form: $("#search-form"),
  query: $("#query"),
  queryError: $("#query-error"),
  searchBtn: $("#search-btn"),
  backBtn: $("#back-btn"),
  results: $("#view-results"),
  resultsTitle: $("#results-title"),
  cards: $("#cards"),
  status: $("#status"),
  parsedInfo: $("#parsed-info"),
  modeBadge: $("#mode-badge"),
  dataMode: $("#data-mode"),
  modeFlag: $(".mode-flag"),
  disclaimer: $("#disclaimer"),
  notes: $("#notes"),
  trace: $("#trace"),
  modal: $("#modal"),
  modalBody: $("#modal-body"),
  modalClose: $("#modal-close"),
  aiStatus: $("#ai-status"),
  aiStatusText: $("#ai-status-text"),
};

// 키 입력·보관은 설정 화면(/settings.html)이 담당하고, 여기서는 읽어 쓰기만 한다.
// 저장 규칙은 key-store.js 단일 출처 — 두 화면이 각자 들고 있으면 조용히 어긋난다.
function readStoredKey() {
  return window.KrcKeyStore ? window.KrcKeyStore.read() : "";
}

/* 검색창 아래 한 줄로 현재 파싱 경로를 알린다 — 어느 쪽으로 검색되는지 감추지 않는다. */
function syncAiStatus() {
  if (!el.aiStatus || !el.aiStatusText) return;
  const has = Boolean(readStoredKey());
  el.aiStatus.dataset.state = has ? "set" : "empty";
  el.aiStatusText.textContent = has
    ? "AI 파싱 켜짐 — 이 탭에 저장된 키를 사용합니다"
    : "AI 파싱 꺼짐 — 규칙 파서로 검색합니다";
  const link = el.aiStatus.querySelector("a");
  if (link) link.textContent = has ? "설정" : "설정에서 키 넣기";
}

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const numberFormatter = new Intl.NumberFormat("ko-KR");
let lastEvidence = [];
let lastDisclaimer = el.disclaimer.textContent;
let searchSequence = 0;

// Icon paths are from Lucide's outline icon set.
const iconPaths = {
  arrowRight: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
  fileSearch: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><circle cx="11.5" cy="14.5" r="2.5"/><path d="m13.3 16.3 1.7 1.7"/>',
  loader: '<path d="M21 12a9 9 0 1 1-6.2-8.6"/>',
  refresh: '<path d="M20 11a8.1 8.1 0 1 0 .5 4"/><path d="M20 4v7h-7"/>',
  searchX: '<path d="m13.5 8.5-5 5"/><path d="m8.5 8.5 5 5"/><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
};

function icon(name) {
  return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + iconPaths[name] + "</svg>";
}

function esc(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, (character) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]
  ));
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function formatNumber(value, suffix = "") {
  if (value == null || value === "") return "확인 불가";
  const number = Number(value);
  return Number.isFinite(number) ? numberFormatter.format(number) + suffix : "확인 불가";
}

function formatBudget(value) {
  if (!value) return "";
  const eok = value / 100000000;
  return "예산 " + (Number.isInteger(eok) ? eok : eok.toFixed(1)) + "억원";
}

function formatEvidenceValue(item) {
  if (item.value == null || item.value === "") return "확인 불가";
  if (typeof item.value !== "number") return String(item.value);
  const units = {
    "분양율": "%",
    "계획세대수": "세대",
    "인구": "명",
    "빈집수": "호",
    "평년대비": "%",
  };
  return formatNumber(item.value, units[item.field] || "");
}

function parsedSummary(parsed) {
  if (!parsed) return "";
  const parts = [];
  if (parsed.region && parsed.region.sido) parts.push(parsed.region.sido);
  if (parsed.region && parsed.region.sigungu) parts.push(parsed.region.sigungu);
  if (parsed.budget_max_krw) parts.push(formatBudget(parsed.budget_max_krw));
  if (Array.isArray(parsed.sale_stage) && parsed.sale_stage.length) parts.push(parsed.sale_stage.join(" / "));
  if (Array.isArray(parsed.preferences) && parsed.preferences.length) parts.push(parsed.preferences.join(", "));
  const confidence = Math.round(clamp(Number(parsed.confidence) || 0, 0, 1) * 100);
  return "해석한 조건 · " + (parts.join(" · ") || "구체적인 조건을 찾지 못했습니다") + " · 해석 신뢰도 " + confidence + "%";
}

function gradeClass(grade) {
  const normalized = String(grade || "D").toUpperCase();
  return ["A", "B", "C", "D"].includes(normalized) ? "grade-" + normalized.toLowerCase() : "grade-d";
}

function droughtStageClass(stage) {
  return stage === "정상" ? "stage-normal" : "";
}

function scrollToElement(target) {
  target.scrollIntoView({ behavior: reduceMotion.matches ? "auto" : "smooth", block: "start" });
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function setLoading(isLoading) {
  el.searchBtn.disabled = isLoading;
  el.searchBtn.classList.toggle("is-loading", isLoading);
  el.searchBtn.setAttribute("aria-busy", String(isLoading));
  el.searchBtn.innerHTML = isLoading
    ? "<span>찾는 중</span>" + icon("loader")
    : "<span>마을 찾기</span>" + icon("arrowRight");
  el.cards.setAttribute("aria-busy", String(isLoading));
}

function renderSkeleton() {
  const card = () => (
    '<article class="skeleton-card" aria-hidden="true">' +
      '<div class="skeleton-line short"></div>' +
      '<div class="skeleton-line title"></div>' +
      '<div class="skeleton-line"></div>' +
      '<div class="skeleton-block"></div>' +
      '<div class="skeleton-line" style="margin-top:28px"></div>' +
      '<div class="skeleton-line short"></div>' +
    "</article>"
  );
  el.cards.innerHTML = card() + card();
}

function droughtHtml(drought) {
  if (!drought) return "";
  const ratio = drought.normal_ratio != null ? " · 평년 대비 " + esc(formatNumber(drought.normal_ratio, "%")) : "";
  return (
    '<div class="drought-panel">' +
      '<strong>지역 농업가뭄 참고</strong> · ' + esc(drought.sigungu || "해당 지역") +
      ' <span class="drought-stage ' + droughtStageClass(drought.drought_stage) + '">' + esc(drought.drought_stage || "확인 불가") + "</span>" + ratio +
      '<span class="note">기준일 ' + esc(drought.base_date || "확인 불가") + " · 마을 적합도 점수에는 반영하지 않습니다.</span>" +
    "</div>"
  );
}

function cardHtml(card, drought, index) {
  const grade = String(card.confidence_grade || "D").toUpperCase();
  const score = Math.round(clamp(Number(card.score) || 0, 0, 1) * 100);
  const titleId = "result-title-" + index;
  const reasons = Array.isArray(card.reasons)
    ? card.reasons.map((reason) => "<li>" + esc(reason) + "</li>").join("")
    : "";

  return (
    '<article class="result-card" aria-labelledby="' + titleId + '">' +
      '<div class="card-top">' +
        "<div>" +
          '<span class="rank">추천 ' + String(index + 1).padStart(2, "0") + "</span>" +
          '<h3 id="' + titleId + '">' + esc(card.gu_name) + "</h3>" +
          '<p class="location">' + esc([card.sido, card.sigungu, card.eupmyeon].filter(Boolean).join(" ")) + "</p>" +
        "</div>" +
        '<div class="badges">' +
          '<span class="badge stage">' + esc(card.sale_stage || "단계 확인 불가") + "</span>" +
          '<span class="badge ' + gradeClass(grade) + '">근거 ' + esc(grade) + "등급</span>" +
        "</div>" +
      "</div>" +
      '<div class="metrics">' +
        '<div class="metric"><div class="key">분양율</div><div class="value">' + esc(formatNumber(card.sale_rate, "%")) + "</div></div>" +
        '<div class="metric"><div class="key">계획세대수</div><div class="value">' + esc(formatNumber(card.planned_households, "세대")) + "</div></div>" +
      "</div>" +
      // 인구·빈집이 둘 다 없으면 줄 자체를 숨긴다 ("확인 불가 · 확인 불가"는 정보가 아니라 노이즈)
      (card.population != null || card.vacant_houses != null
        ? '<p class="village-summary">마을 현황 · 인구 ' + esc(formatNumber(card.population, "명")) + " · 빈집 " + esc(formatNumber(card.vacant_houses, "호")) + "</p>"
        : "") +
      (reasons ? '<ul class="reasons" aria-label="선정 이유">' + reasons + "</ul>" : "") +
      '<div class="score-row"><span>조건 적합도</span><strong>' + score + "%</strong></div>" +
      '<div class="score-bar" role="progressbar" aria-label="조건 적합도" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + score + '">' +
        '<div class="score-fill" style="width:' + score + '%"></div>' +
      "</div>" +
      droughtHtml(drought && drought.sigungu === card.sigungu ? drought : null) +
      '<div class="card-actions">' +
        '<button class="evidence-button" type="button" data-gu="' + esc(card.gu_name) + '">' + icon("fileSearch") + "수치 근거 확인</button>" +
      "</div>" +
    "</article>"
  );
}

function renderWarnings(warnings) {
  const messages = Array.isArray(warnings) ? warnings.filter(Boolean) : [];
  if (!messages.length) {
    el.status.innerHTML = "";
    return;
  }
  el.status.innerHTML = (
    '<div class="warning-panel">' +
      "<strong>확인할 내용이 있습니다.</strong>" +
      messages.map((message) => "<p>" + esc(message) + "</p>").join("") +
    "</div>"
  );
}

function renderNotes(notes) {
  if (!el.notes) return;
  const messages = Array.isArray(notes) ? notes.filter(Boolean) : [];
  // 안내는 '문제'가 아니므로 경고 패널과 분리해 조용한 메모로 표시한다.
  el.notes.innerHTML = messages.length
    ? '<div class="notes-panel">' +
        messages.map((message) => "<p>" + esc(message) + "</p>").join("") +
      "</div>"
    : "";
}

/* 계산 내역 — "왜 이 결과인가"를 이 검색 한 건의 실제 숫자로 보여준다.
   기본은 접힘: 궁금한 사람만 열게 하고 검색 흐름을 가리지 않는다. */
function renderTrace(trace) {
  if (!el.trace) return;
  if (!trace || !Array.isArray(trace.funnel) || !trace.funnel.length) {
    el.trace.innerHTML = "";
    return;
  }

  const funnel = trace.funnel.map((step, i) => {
    const drop = step.dropped > 0
      ? '<span class="trace-drop">−' + esc(String(step.dropped)) + "</span>"
      : "";
    const note = step.note ? '<span class="trace-note">' + esc(step.note) + "</span>" : "";
    return (
      '<li><span class="trace-step">' + esc(String(i + 1)) + "</span>" +
        '<span class="trace-label">' + esc(step.label) + note + "</span>" +
        '<span class="trace-count">' + esc(formatNumber(step.count, "건")) + drop + "</span>" +
      "</li>"
    );
  }).join("");

  const scores = (trace.scores || []).map((card) => {
    const rows = (card.terms || []).map((term) =>
      "<tr><th>" + esc(term.label) + "</th>" +
        "<td>" + esc(String(term.weight)) + " × " + esc(String(term.value)) +
          " = <strong>" + esc(String(term.contribution)) + "</strong></td>" +
        '<td class="trace-basis">' + esc(term.basis || "") + "</td></tr>"
    ).join("");
    return (
      '<div class="trace-score">' +
        "<h4>" + esc(card.gu_name) + ' <span>합계 ' + esc(String(card.total)) + "</span></h4>" +
        '<table><tbody>' + rows + "</tbody></table>" +
      "</div>"
    );
  }).join("");

  el.trace.innerHTML = (
    '<details class="trace-panel">' +
      "<summary>이 결과가 나온 계산 보기</summary>" +
      '<div class="trace-body">' +
        '<dl class="trace-meta">' +
          "<dt>문장을 조건으로 바꾼 주체</dt><dd>" + esc(trace.parser) + "</dd>" +
          "<dt>AI가 관여한 범위</dt><dd>" + esc(trace.llm_scope) + "</dd>" +
          "<dt>점수 산식</dt><dd><code>" + esc(trace.formula) + "</code></dd>" +
        "</dl>" +
        "<h3>후보가 좁혀진 과정</h3>" +
        '<ol class="trace-funnel">' + funnel + "</ol>" +
        // 0건 검색에서도 funnel은 '왜 0건인지'를 설명하므로 그린다.
        // 다만 점수 계산은 채울 내용이 없으므로 제목까지 통째로 뺀다 —
        // 빈 제목만 남으면 패널이 뭔가 빠진 것처럼 보인다.
        (scores ? "<h3>점수 계산</h3>" + scores : "") +
        '<p class="trace-foot">' +
          (trace.deterministic
            ? "같은 문장으로 다시 검색하면 같은 값이 나옵니다 — 조건 해석부터 순위까지 전부 규칙 기반입니다. "
            : "순위와 점수는 위 산식이 정하며 모델은 관여하지 않습니다. 다만 문장을 조건으로 바꾸는 단계에 AI를 썼기 때문에, " +
              "같은 문장이라도 해석이 달라져 결과가 바뀔 수 있습니다. 항상 같은 결과를 원하시면 " +
              '<a href="/settings.html">설정</a>에서 키를 지우세요. ') +
          "이 내역은 응답에만 담기며 서버에 저장하지 않습니다.</p>" +
      "</div>" +
    "</details>"
  );
}

function renderEmpty(message) {
  el.resultsTitle.setAttribute("aria-label", "조건에 맞는 전원마을을 찾지 못했습니다.");
  el.cards.innerHTML = (
    '<div class="empty-state">' +
      icon("searchX") +
      "<h3>조건에 맞는 마을을 찾지 못했습니다.</h3>" +
      "<p>" + esc(message || "지역이나 분양 단계를 조금 넓혀 다시 검색해 보세요.") + "</p>" +
      '<button class="retry-button" type="button" data-action="refine">조건 다시 입력</button>' +
    "</div>"
  );
}

function renderError(error) {
  const timedOut = error && error.name === "AbortError";
  const message = timedOut
    ? "응답 시간이 길어 검색을 중단했습니다. 잠시 후 다시 시도해 주세요."
    : "검색 서버에 연결하지 못했습니다. 서버 상태를 확인한 뒤 다시 시도해 주세요.";
  el.resultsTitle.setAttribute("aria-label", "검색을 완료하지 못했습니다.");
  el.status.className = "status error";
  el.status.textContent = message;
  // 실패한 검색 화면에 직전 검색의 계산 내역이 남으면 그 자체가 거짓 표시가 된다
  renderTrace(null);
  renderNotes([]);
  el.cards.innerHTML = (
    '<div class="empty-state">' +
      icon("refresh") +
      "<h3>검색을 완료하지 못했습니다.</h3>" +
      "<p>" + esc(message) + "</p>" +
      '<button class="retry-button" type="button" data-action="retry">' + icon("refresh") + "다시 검색</button>" +
    "</div>"
  );
}

function openEvidence(guName) {
  const prefix = "[" + guName + "]";
  const rows = lastEvidence.filter((item) => item.claim && item.claim.startsWith(prefix));
  const rowHtml = rows.length
    ? rows.map((item) => (
        "<tr>" +
          "<td>" + esc(String(item.claim).replace(prefix, "").trim()) + "</td>" +
          "<td>" + esc(item.api) + "</td>" +
          "<td>" + esc(item.field) + "</td>" +
          "<td>" + esc(formatEvidenceValue(item)) + "</td>" +
        "</tr>"
      )).join("")
    : '<tr><td colspan="4">이 마을에 연결된 수치 근거가 없습니다.</td></tr>';

  el.modalBody.innerHTML = (
    '<div class="evidence-summary"><strong>' + esc(guName) + "</strong><span>확인된 필드 " + rows.length + "개</span></div>" +
    '<div class="table-wrap"><table aria-label="' + esc(guName) + ' 수치 근거">' +
      "<thead><tr><th>확인 내용</th><th>API</th><th>원본 필드</th><th>값</th></tr></thead>" +
      "<tbody>" + rowHtml + "</tbody>" +
    "</table></div>" +
    '<div class="modal-disclaimer">' + esc(lastDisclaimer) + "</div>"
  );
  el.modal.showModal();
}

async function runSearch() {
  const query = el.query.value.trim();
  if (!query) {
    el.queryError.hidden = false;
    el.query.setAttribute("aria-invalid", "true");
    el.query.focus();
    return;
  }

  const sequence = ++searchSequence;
  el.queryError.hidden = true;
  el.query.removeAttribute("aria-invalid");
  el.results.hidden = false;
  el.status.className = "status";
  el.status.textContent = "공공데이터에서 조건에 맞는 후보를 확인하고 있습니다.";
  el.parsedInfo.textContent = "";
  renderSkeleton();
  setLoading(true);
  scrollToElement(el.results);

  try {
    const apiKey = readStoredKey();
    const payload = { query };
    if (apiKey) payload.openai_api_key = apiKey;   // 없으면 필드 자체를 보내지 않는다

    const response = await fetchWithTimeout("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error("HTTP " + response.status);
    const data = await response.json();
    if (sequence !== searchSequence) return;

    lastEvidence = Array.isArray(data.evidence) ? data.evidence : [];
    lastDisclaimer = data.disclaimer || lastDisclaimer;
    el.disclaimer.textContent = lastDisclaimer;
    el.parsedInfo.textContent = parsedSummary(data.query_parsed);
    renderWarnings(data.warnings);
    renderNotes(data.notes);
    renderTrace(data.trace);

    const results = Array.isArray(data.top) ? data.top : [];
    if (!results.length) {
      renderEmpty();
    } else {
      el.cards.innerHTML = results.map((card, index) => cardHtml(card, data.drought_panel, index)).join("");
      const countMessage = results.length + "곳을 찾았습니다. 각 카드에서 사용한 데이터 근거를 확인할 수 있습니다.";
      el.resultsTitle.setAttribute("aria-label", countMessage);
    }
    el.resultsTitle.focus({ preventScroll: true });
  } catch (error) {
    if (sequence === searchSequence) renderError(error);
  } finally {
    if (sequence === searchSequence) setLoading(false);
  }
}

async function loadHealth() {
  try {
    const response = await fetchWithTimeout("/api/health", { headers: { Accept: "application/json" } }, 5000);
    if (!response.ok) throw new Error("HTTP " + response.status);
    const health = await response.json();
    const live = !health.sample_mode;
    if (el.modeBadge) el.modeBadge.classList.toggle("is-live", live);
    if (el.dataMode) el.dataMode.textContent = live ? "공공데이터 연결 모드" : "샘플 데이터로 체험 중";
    // 푸터 표시는 하드코딩이었다 — 실제 모드와 어긋나면 서비스가 거짓말을 하게 된다.
    if (el.modeFlag) el.modeFlag.textContent = live ? "공공데이터 연결 모드로 동작 중" : "sample-mode로 동작 중";
  } catch (_error) {
    if (el.modeBadge) el.modeBadge.classList.add("is-error");
    if (el.dataMode) el.dataMode.textContent = "데이터 상태 확인 불가";
    if (el.modeFlag) el.modeFlag.textContent = "데이터 상태 확인 불가";
  }
}

el.form.addEventListener("submit", (event) => {
  event.preventDefault();
  runSearch();
});

el.query.addEventListener("input", () => {
  if (el.query.value.trim()) {
    el.queryError.hidden = true;
    el.query.removeAttribute("aria-invalid");
  }
});

document.querySelectorAll(".query-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    el.query.value = chip.dataset.query || chip.textContent.trim();
    el.form.requestSubmit();
  });
});

el.backBtn.addEventListener("click", () => {
  scrollToElement($("#search"));
  window.setTimeout(() => el.query.focus(), reduceMotion.matches ? 0 : 450);
});

el.cards.addEventListener("click", (event) => {
  const evidenceButton = event.target.closest(".evidence-button");
  if (evidenceButton) {
    openEvidence(evidenceButton.dataset.gu || "선택한 마을");
    return;
  }

  const actionButton = event.target.closest("[data-action]");
  if (!actionButton) return;
  if (actionButton.dataset.action === "retry") runSearch();
  if (actionButton.dataset.action === "refine") {
    scrollToElement($("#search"));
    window.setTimeout(() => el.query.focus(), reduceMotion.matches ? 0 : 450);
  }
});

// --- AI 파싱 상태 표시 ---
syncAiStatus();
// 설정 화면에서 키를 바꾸고 뒤로 돌아왔을 때 표시가 낡지 않도록 갱신한다.
// (bfcache 복원은 pageshow로만 잡히고 visibilitychange는 탭 전환도 잡는다)
window.addEventListener("pageshow", syncAiStatus);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) syncAiStatus();
});

el.modalClose.addEventListener("click", () => el.modal.close());
el.modal.addEventListener("click", (event) => {
  if (event.target === el.modal) el.modal.close();
});

loadHealth();
