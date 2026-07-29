"use strict";

const $ = (selector, root = document) => root.querySelector(selector);

const el = {
  form: $("#search-form"),
  query: $("#query"),
  queryError: $("#query-error"),
  searchBtn: $("#search-btn"),
  backBtn: $("#back-btn"),
  traceOpen: $("#trace-open"),
  results: $("#view-results"),
  resultsTitle: $("#results-title"),
  resultsLead: $("#results-lead"),
  tieNote: $("#tie-note"),
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
  regionFilter: $("#region-filter"),
  selSido: $("#sel-sido"),
  selSigungu: $("#sel-sigungu"),
  selStage: $("#sel-stage"),
  regionReset: $("#region-reset"),
};

// /api/regions 응답. 로드 전이거나 실패하면 null이고, 그 경우 지역 선택 UI는
// 숨긴 채로 둔다 — 자연어 검색만으로도 서비스는 완전히 동작한다.
let regionData = null;

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

function parsedSummary(parsed, isStructured) {
  if (!parsed) return "";
  const parts = [];
  if (parsed.region && parsed.region.sido) parts.push(parsed.region.sido);
  if (parsed.region && parsed.region.sigungu) parts.push(parsed.region.sigungu);
  if (parsed.budget_max_krw) parts.push(formatBudget(parsed.budget_max_krw));
  if (Array.isArray(parsed.sale_stage) && parsed.sale_stage.length) parts.push(parsed.sale_stage.join(" / "));
  if (Array.isArray(parsed.preferences) && parsed.preferences.length) parts.push(parsed.preferences.join(", "));
  // 목록에서 직접 고른 조건에 "해석 신뢰도"를 붙이면 거짓이다 — 해석한 적이 없다.
  if (isStructured) {
    return "선택한 조건 · " + (parts.join(" · ") || "전체") + " · 문장 해석 없음";
  }
  const confidence = Math.round(clamp(Number(parsed.confidence) || 0, 0, 1) * 100);
  return "해석한 조건 · " + (parts.join(" · ") || "구체적인 조건을 찾지 못했습니다") + " · 해석 신뢰도 " + confidence + "%";
}

function gradeClass(grade) {
  const normalized = String(grade || "D").toUpperCase();
  return ["A", "B", "C", "D"].includes(normalized) ? "grade-" + normalized.toLowerCase() : "grade-d";
}

/** 등급 배지의 문구.
 *
 * "근거 A등급"이라고 쓰고 있었지만 A/B/C가 재는 것은 근거의 품질이 아니라
 * **농촌마을현황이 이 지구에 얼마나 정확히 붙었는가**다(법정동코드 완전일치=A,
 * 시군구만 일치=B, 못 붙임=C). 라벨과 실제 의미가 다르면 배지가 정보가 아니라
 * 장식이 된다 — 재는 것을 그대로 쓴다.
 */
const GRADE_TEXT = {
  A: { label: "마을 상세 일치", title: "법정동코드가 정확히 일치해 인구·빈집을 이 마을 값으로 표시합니다." },
  B: { label: "시군구 근사", title: "법정동코드는 다르고 시군구만 같습니다 — 마을 상세는 참고값입니다." },
  C: { label: "마을 상세 없음", title: "붙는 마을현황 레코드가 없어 인구·빈집을 표시하지 않습니다." },
  D: { label: "마을 상세 없음", title: "붙는 마을현황 레코드가 없어 인구·빈집을 표시하지 않습니다." },
};

function gradeText(grade) {
  return GRADE_TEXT[String(grade || "D").toUpperCase()] || GRADE_TEXT.D;
}

function droughtStageClass(stage) {
  return stage === "정상" ? "stage-normal" : "";
}

function scrollToElement(target) {
  if (reduceMotion.matches) {
    target.scrollIntoView({ behavior: "instant", block: "start" });
    return;
  }
  target.scrollIntoView({ behavior: "smooth", block: "start" });
  // 부드러운 스크롤은 시작조차 하지 않는 경우가 있다(실측: 배포본에서 클릭 후 5초간 12px).
  // 그러면 결과가 화면 밖에 남아 "검색했는데 아무 일도 안 일어난" 화면이 된다.
  // 애니메이션에 맡기되, 도달했는지 확인하고 어긋나면 즉시 이동으로 마무리한다.
  window.setTimeout(() => {
    const offset = target.getBoundingClientRect().top;
    if (Math.abs(offset) > 8) {
      window.scrollTo({ top: window.scrollY + offset, behavior: "instant" });
    }
  }, 700);
}

/** 결과가 있으면 히어로를 검색 바로 접는다.
 *
 * 펼친 히어로는 880px라 결과가 항상 첫 화면 밖에 남는다. 그 간격을 스크롤
 * 애니메이션 하나로 메우는 구조는 애니메이션이 어긋나는 순간 기능이 통째로
 * 안 보인다 — 애초에 먼 거리를 만들지 않는 편이 확실하다.
 */
function setResultsMode(on) {
  document.body.classList.toggle("results-mode", on);
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

/** 카드의 수치 한 칸.
 *
 * 값이 없을 때 "확인 불가"를 실제 수치와 같은 크기로 찍으면, 원천 데이터의 84%가
 * 비어 있는 분양율 탓에 카드에서 가장 큰 글씨가 매번 "확인 불가"가 된다.
 * 고지는 유지하되 크기를 낮춰, 있는 값이 먼저 읽히게 한다.
 */
/** 값이 없는 지표의 사유. 카드에서 바로 보여야 한다.
 *
 * 사유는 접힌 "데이터 한계"에도 적혀 있지만 펼치지 않으면 안 보인다. 실제로
 * "분양율이 왜 다 확인 불가냐 — API를 못 가져오는 거냐"는 질문이 나왔다.
 * 답은 '못 가져온다'가 아니라 '원천이 비어 있다'이고, 그 차이가 중요하다.
 */
const UNKNOWN_REASON = {
  분양율: "원천 미입력 (167건 중 141건이 0)",
  계획세대수: "원천 미입력",
};

function metricHtml(key, value, suffix) {
  const unknown = value == null;
  const reason = unknown && UNKNOWN_REASON[key]
    ? '<div class="metric-reason">' + esc(UNKNOWN_REASON[key]) + "</div>"
    : "";
  return (
    '<div class="metric' + (unknown ? " is-unknown" : "") + '">' +
      '<div class="key">' + esc(key) + "</div>" +
      '<div class="value">' + esc(formatNumber(value, suffix)) + "</div>" +
      reason +
    "</div>"
  );
}

/** 지표 칸 정렬 — 값이 있는 것을 앞에 둔다.
 *
 * 분양율은 원천의 84%가 비어 있어 고정 순서로 두면 카드 첫 칸이 매번
 * "확인 불가"가 된다. 있는 값이 먼저 읽혀야 카드가 정보로 보인다.
 * 값이 둘 다 있으면 원래 순서(분양율 → 계획세대수)를 유지한다.
 */
function metricsHtml(card) {
  const metrics = [
    { key: "분양율", value: card.sale_rate, suffix: "%" },
    { key: "계획세대수", value: card.planned_households, suffix: "세대" },
  ];
  const known = metrics.filter((m) => m.value != null);
  const unknown = metrics.filter((m) => m.value == null);
  return known.concat(unknown).map((m) => metricHtml(m.key, m.value, m.suffix)).join("");
}

/** 점수 옆 산식 요약 — "왜 75%인가"에 카드에서 바로 답한다.
 *
 * 계산 내역 패널에도 같은 내용이 있지만 그건 펼쳐야 보인다. 점수만 덩그러니
 * 있으면 근거 없는 숫자로 읽히고, 이 서비스가 가장 피하려는 인상이 그것이다.
 */
function scoreFormula(terms) {
  if (!Array.isArray(terms) || !terms.length) return "";
  const parts = terms.map((t) => esc(t.label) + " " + esc(String(t.contribution)));
  return '<p class="score-formula">' + parts.join(" + ") + "</p>";
}

function cardHtml(card, drought, index, terms) {
  const grade = String(card.confidence_grade || "D").toUpperCase();
  const badge = gradeText(grade);
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
          '<span class="badge ' + gradeClass(grade) + '" title="' + esc(badge.title) + '">' +
            esc(badge.label) + "</span>" +
        "</div>" +
      "</div>" +
      '<div class="metrics">' + metricsHtml(card) + "</div>" +
      // 인구·빈집이 둘 다 없으면 줄 자체를 숨긴다 ("확인 불가 · 확인 불가"는 정보가 아니라 노이즈)
      (card.population != null || card.vacant_houses != null
        ? '<p class="village-summary">' +
            "<strong>주변 마을" + (card.village_name ? " " + esc(card.village_name) : "") + "</strong> · " +
            "인구 " + esc(formatNumber(card.population, "명")) +
            " · 빈집 " + esc(formatNumber(card.vacant_houses, "호")) +
            '<span class="village-note">이 지구가 아니라 같은 법정동 마을의 현황입니다 — 적합도 점수에 반영하지 않습니다.</span>' +
          "</p>"
        : "") +
      (reasons ? '<ul class="reasons" aria-label="선정 이유">' + reasons + "</ul>" : "") +
      '<div class="score-row"><span>조건 적합도</span><strong>' + score + "%</strong></div>" +
      '<div class="score-bar" role="progressbar" aria-label="조건 적합도" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + score + '">' +
        '<div class="score-fill" style="width:' + score + '%"></div>' +
      "</div>" +
      scoreFormula(terms) +
      droughtHtml(drought && drought.sigungu === card.sigungu ? drought : null) +
      '<div class="card-actions">' +
        '<button class="evidence-button" type="button" data-gu="' + esc(card.gu_name) + '">' + icon("fileSearch") + "수치 근거 확인</button>" +
      "</div>" +
    "</article>"
  );
}

function resetResultsHeading(title) {
  el.resultsTitle.textContent = title;
  el.resultsLead.textContent = "";
  if (el.tieNote) {
    el.tieNote.textContent = "";
    el.tieNote.hidden = true;
  }
}

/** 결과 제목을 실제 정보로 채운다.
 *
 * "조건에 맞는 전원마을"은 어떤 검색에도 똑같이 붙는 문구라 46px를 쓰고도
 * 알려주는 게 없었다. 정작 알아야 할 숫자(전국 몇 곳 중 몇 곳)는 그 아래
 * 회색 한 줄에 묻혀 있었다 — 자리를 맞바꾼다.
 *
 * 숫자는 trace.funnel에서 가져온다. 카드 개수만 세면 "상위 3건 표시" 제한에
 * 걸린 값이라 실제 조건 충족 건수와 다르다.
 */
function renderResultsHeading(parsed, trace, shown) {
  const region = [parsed && parsed.region && parsed.region.sido,
                  parsed && parsed.region && parsed.region.sigungu].filter(Boolean).join(" ");
  el.resultsTitle.textContent = (region ? region + " " : "") + shown + "곳";

  const funnel = (trace && Array.isArray(trace.funnel)) ? trace.funnel : [];
  const total = funnel.length ? funnel[0].count : null;
  // 마지막 단계는 "상위 N건 표시" 제한이므로 그 직전이 조건 충족 건수다
  const matched = funnel.length >= 2 ? funnel[funnel.length - 2].count : null;

  const bits = [];
  if (total != null) bits.push("전국 " + formatNumber(total, "곳"));
  if (matched != null) bits.push("조건 충족 " + formatNumber(matched, "곳"));
  if (matched != null && matched > shown) bits.push("상위 " + shown + "곳 표시");
  el.resultsLead.textContent = bits.join(" · ");

  el.resultsTitle.setAttribute(
    "aria-label",
    shown + "곳을 찾았습니다. " + el.resultsLead.textContent +
    ". 각 카드에서 사용한 데이터 근거를 확인할 수 있습니다.");
}

/** 표시된 카드의 점수가 전부 같으면 번호는 순위가 아니다.
 *
 * 실제로 "추천 01/02/03"이 붙은 세 장이 전부 75%인 경우가 흔하다(분양율이
 * 비어 중립값이 들어가고 선호 조건이 없으면 진행단계만 남는다). 번호를 그대로
 * 두면 없는 우열을 주장하는 셈이라, 동점이면 그 사실을 밝힌다.
 */
function renderTieNote(cards) {
  if (!el.tieNote) return;
  const scores = cards.map((c) => Math.round(clamp(Number(c.score) || 0, 0, 1) * 100));
  const tied = scores.length > 1 && scores.every((s) => s === scores[0]);
  el.tieNote.textContent = tied
    ? "표시된 " + scores.length + "곳의 적합도가 " + scores[0] + "%로 같습니다 — 번호는 순위가 아니라 표시 순서입니다."
    : "";
  el.tieNote.hidden = !tied;
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
  //
  // 접어 두되 건수는 항상 보인다. 펼친 채로 두면 조밀한 고지 3줄이 카드보다
  // 먼저 나와 첫인상이 변명이 되고, 통째로 빼면 그 순간 정직성이 깨진다 —
  // "몇 건 있다"를 항상 보이게 두는 편이 양쪽을 다 지킨다.
  el.notes.innerHTML = messages.length
    ? '<details class="notes-panel">' +
        "<summary>이 결과의 데이터 한계 " + messages.length + "건</summary>" +
        '<div class="notes-body">' +
          messages.map((message) => "<p>" + esc(message) + "</p>").join("") +
        "</div>" +
      "</details>"
    : "";
}

/* 계산 내역 — "왜 이 결과인가"를 이 검색 한 건의 실제 숫자로 보여준다.
   기본은 접힘: 궁금한 사람만 열게 하고 검색 흐름을 가리지 않는다. */
function renderTrace(trace) {
  if (!el.trace) return;
  if (!trace || !Array.isArray(trace.funnel) || !trace.funnel.length) {
    el.trace.innerHTML = "";
    if (el.traceOpen) el.traceOpen.hidden = true;
    return;
  }
  if (el.traceOpen) el.traceOpen.hidden = false;

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

  // 요약줄에 "몇 건에서 몇 건으로 좁혔는지"를 먼저 보인다 — 펼치기 전에도
  // 이 패널이 무엇을 담고 있는지 알 수 있어야 열어볼 이유가 생긴다.
  const first = trace.funnel[0];
  const last = trace.funnel[trace.funnel.length - 1];
  const span = first && last && first.count != null && last.count != null
    ? '<span class="trace-summary-count">' +
        esc(formatNumber(first.count, "건")) + " → " + esc(formatNumber(last.count, "건")) +
      "</span>"
    : "";

  el.trace.innerHTML = (
    '<details class="trace-panel" id="trace-panel">' +
      '<summary><span class="trace-summary-title">계산 내역 · 이 결과가 나온 과정</span>' + span + "</summary>" +
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
  // 제목·부제가 동적이라 직전 검색의 "전라남도 3곳"이 남으면 0건 화면과 정면으로 어긋난다
  resetResultsHeading("조건에 맞는 곳 없음");
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
  resetResultsHeading("검색 실패");
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

// --- 지역 드롭다운 (자연어 입력의 대안 경로) ---

/** 선택된 값들을 백엔드 ParsedQuery 형태로 만든다.
 *
 * 문장으로 바꿔 파서에 다시 태우지 않는 이유: 사용자가 목록에서 직접 고른
 * 값은 이미 확정된 조건이다. 그걸 다시 문장으로 만들어 해석시키면 추측이
 * 한 단계 끼어든다 — 실제로 "예산"을 시군구와 예산(금액)으로 동시에 읽어
 * 결과가 0건이 된 적이 있다. 서버의 structured 경로가 파싱을 건너뛴다.
 */
function structuredFromSelects() {
  const sido = el.selSido.value;
  const sigungu = el.selSigungu.value;
  const stage = el.selStage.value;
  if (!sido && !sigungu && !stage) return null;
  return {
    region: { sido: sido || null, sigungu: sigungu || null },
    budget_max_krw: null,
    sale_stage: stage ? [stage] : [],
    household_min: null,
    preferences: [],
    confidence: 1,                    // 해석한 값이 아니라 사용자가 고른 값
    raw: [sido, sigungu, stage].filter(Boolean).join(" "),
  };
}

function hasRegionSelection() {
  return Boolean(el.selSido.value || el.selSigungu.value || el.selStage.value);
}

function option(value, label) {
  const o = document.createElement("option");
  o.value = value;
  o.textContent = label;
  return o;
}

function fillSigungu(sidoName) {
  const sido = (regionData.시도 || []).find((s) => s.이름 === sidoName);
  const list = sido ? sido.시군구 || [] : [];
  el.selSigungu.replaceChildren(option("", "시군구 전체"));
  list.forEach((g) => el.selSigungu.appendChild(option(g.이름, g.이름 + " (" + g.건수 + ")")));
  el.selSigungu.disabled = list.length === 0;
}

function syncRegionReset() {
  el.regionReset.hidden = !hasRegionSelection();
}

function clearRegionSelects() {
  el.selSido.value = "";
  el.selStage.value = "";
  el.selSigungu.replaceChildren(option("", "시군구 전체"));
  el.selSigungu.disabled = true;
  syncRegionReset();
}

async function loadRegions() {
  try {
    const response = await fetchWithTimeout("/api/regions", {}, 25000);
    if (!response.ok) return;
    const data = await response.json();
    if (!Array.isArray(data.시도) || !data.시도.length) return;

    regionData = data;
    el.selSido.replaceChildren(option("", "시도 전체"));
    data.시도.forEach((s) => el.selSido.appendChild(option(s.이름, s.이름 + " (" + s.건수 + ")")));
    el.selStage.replaceChildren(option("", "진행단계 전체"));
    (data.진행단계 || []).forEach((s) =>
      el.selStage.appendChild(option(s.이름, s.이름 + " (" + s.건수 + ")")));
    el.regionFilter.hidden = false;
  } catch (error) {
    // 지역 선택은 보조 수단 — 실패하면 조용히 숨긴 채로 두고 자연어 검색을 남긴다
  }
}

async function runSearch() {
  // 드롭다운에 선택이 있으면 그게 조건이다 (자연어와 상호 배타 — 아래 이벤트에서 보장)
  const structured = structuredFromSelects();
  const query = el.query.value.trim();
  if (!structured && !query) {
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
  setResultsMode(true);
  // 히어로가 접히면 결과는 이미 첫 화면 안에 들어온다. 여기서 결과로 스크롤하면
  // 접힌 검색창까지 화면 위로 밀려나 조건을 고칠 수단이 사라진다 — 맨 위를 유지한다.
  window.scrollTo({ top: 0, behavior: "instant" });

  try {
    const apiKey = readStoredKey();
    // structured면 서버가 문장 파싱을 건너뛴다 — LLM 키도 쓸 일이 없으므로 보내지 않는다
    const payload = structured ? { structured } : { query };
    if (apiKey && !structured) payload.openai_api_key = apiKey;

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
    el.parsedInfo.textContent = parsedSummary(data.query_parsed, Boolean(structured));
    renderWarnings(data.warnings);
    renderNotes(data.notes);
    renderTrace(data.trace);

    const results = Array.isArray(data.top) ? data.top : [];
    if (!results.length) {
      renderEmpty();
    } else {
      // trace.scores는 카드와 1:1로 짝지어 오므로 인덱스로 산식을 붙인다
      const scores = (data.trace && Array.isArray(data.trace.scores)) ? data.trace.scores : [];
      el.cards.innerHTML = results
        .map((card, index) => cardHtml(card, data.drought_panel, index,
                                       scores[index] && scores[index].terms))
        .join("");
      renderResultsHeading(data.query_parsed, data.trace, results.length);
      renderTieNote(results);
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
    // 둘 다 값이 있으면 무엇이 조건인지 화면만 봐서는 알 수 없다 —
    // 마지막에 손댄 쪽을 조건으로 삼고 다른 쪽은 비운다.
    if (hasRegionSelection()) clearRegionSelects();
  }
});

el.selSido.addEventListener("change", () => {
  fillSigungu(el.selSido.value);
  el.query.value = "";
  el.queryError.hidden = true;
  syncRegionReset();
  runSearch();
});

el.selSigungu.addEventListener("change", () => {
  el.query.value = "";
  syncRegionReset();
  runSearch();
});

el.selStage.addEventListener("change", () => {
  el.query.value = "";
  el.queryError.hidden = true;
  syncRegionReset();
  runSearch();
});

el.regionReset.addEventListener("click", () => {
  clearRegionSelects();
  el.query.focus();
});

document.querySelectorAll(".query-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    el.query.value = chip.dataset.query || chip.textContent.trim();
    el.form.requestSubmit();
  });
});

el.backBtn.addEventListener("click", () => {
  setResultsMode(false);          // 히어로를 다시 펼친다 (검색 화면으로 복귀)
  scrollToElement($("#search"));
  window.setTimeout(() => el.query.focus(), reduceMotion.matches ? 0 : 450);
});

el.traceOpen.addEventListener("click", () => {
  const panel = $("#trace-panel");
  if (!panel) return;
  panel.open = true;
  scrollToElement(panel);
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
    setResultsMode(false);        // 조건을 고치려면 히어로의 입력창이 다시 필요하다
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
loadRegions();
