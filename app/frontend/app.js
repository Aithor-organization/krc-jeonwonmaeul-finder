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
  seeAll: $("#see-all"),
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
  regionHint: $("#region-hint"),
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
let lastCards = [];   // 모달이 주소·지구명을 쓰려면 카드 원본이 필요하다
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
  분양율: "이 지구 값이 원천에 없음 (전국 167곳 중 141곳이 같음)",
  계획세대수: "이 지구 값이 원천에 없음",
};

/** 지표가 무엇의 값인지. 🔴 이 카드에서 가장 헷갈리는 지점이다.
 *
 * "분양율 / 확인 불가 / 원천 미입력 (167건 중 141건이 0)"을 그대로 쌓아 두면
 * 위는 이 지구 하나의 값인데 아래는 전국 통계라, 한 칸 안에서 단위가 뒤바뀐다.
 * 실제로 "여기 분양율이 이 지구 얘기냐 지역 얘기냐"는 질문이 나왔다.
 *
 * 지역 값이 아니라는 것은 원천으로 확인된다 — 강원 원주시에 100%인 지구
 * (지정새싹)와 0%인 지구(서곡)가 함께 있다. 이렇게 한 시군구 안에서 값이
 * 갈리는 곳이 9곳이다. 지역 단위였다면 같은 값이어야 한다.
 */
const METRIC_SCOPE = {
  분양율: "이 지구의 계획세대수 대비 분양된 비율입니다. 시군구·지역 전체 값이 아닙니다.",
  계획세대수: "이 지구에 새로 조성되는 세대 수 — 실제로 분양받는 대상입니다.",
};

/** 값이 있을 때 붙는 한 줄. "이게 뭔데?"에 그 자리에서 답한다.
 *
 * 🔴 "빈집이 없는데 왜 추천하냐"는 질문이 나왔다. 전원마을 조성사업은
 * **새 택지를 닦고 주택을 분양하는 신규마을 조성**이라(농식품부 「신규마을조성
 * (전원마을 등)」), 들어가는 집은 이 지구에 새로 짓는 것이지 옆 마을의
 * 빈집이 아니다. 그런데 카드가 "계획세대수 31세대"라고만 적어 두고 그게
 * 분양 대상이라는 말을 안 했다 — 그래서 빈집이 들어갈 집으로 읽혔다.
 */
const METRIC_HINT = {
  계획세대수: "이 지구에 새로 조성 — 분양 대상",
};

/** 분양율 수치가 없어도 진행단계가 답을 주는 경우가 있다.
 *
 * "분양율을 아예 모르는 거냐"는 질문에 대한 답 — 수치는 모르지만 분양완료면
 * 남은 자리가 없다는 건 안다(수치가 기록된 완료 지구 6건 전부 100%).
 * 그 판단은 점수에도 반영되므로(가용성 0), 카드에도 같은 말을 적는다.
 */
function unknownRateReason(card) {
  // 🔴 '없음'과 '범위를 벗어남'은 화면에서 같은 "확인 불가"로 보이지만 이유가
  // 다르다. 구례 남도는 원천에 150%가 적혀 있는데(계획 20세대) "원천에 값이
  // 없음"이라고 말하면 그건 사실이 아니다. 값이 있었다는 것과, 그 값을 믿지
  // 못해 보류했다는 것을 그대로 적는다.
  const over = card.sale_rate_out_of_range;
  if (over != null) {
    return "원천 기록은 " + String(over) + "%지만 100%를 넘어 표시를 보류했습니다";
  }
  const stage = card.sale_stage;
  if (stage === "분양완료") return "이 지구는 수치 미입력이지만 분양완료 — 남은 자리 없음";
  if (stage === "분양예정") return "이 지구는 분양 시작 전이라 기록 없음";
  return UNKNOWN_REASON.분양율;
}

/** 분양율을 얼마나 믿을 수 있는가 — 네 상태를 눈에 보이게 가른다.
 *
 * 🔴 전에는 둘뿐이었다: 수치가 있으면 표시, 없으면 "확인 불가". 그래서
 * **우리가 아는 17건이 정말 모르는 124건과 똑같은 칸**에 들어갔다.
 * 분양완료 지구는 수치가 없어도 남은 자리가 없다는 걸 알고, 그 판단을
 * 점수(가용성 0)에는 이미 쓰면서 화면에서만 감추고 있었다.
 *
 * ⚠️ 그래도 '추정'을 숫자 100%로 적지 않는다. 100%가 분양예정 단계에도
 * 12건 있어서 그 값의 의미 자체가 확실하지 않다. 아는 것은 "남은 자리 없음"
 * 이라는 판정이지 "100%"라는 수치가 아니다.
 */
const RATE_STATUS = {
  확정: { label: "원천 기록", cls: "is-confirmed" },
  추정: { label: "단계로 추정", cls: "is-inferred" },
  보류: { label: "값 보류", cls: "is-held" },
  미상: { label: "기록 없음", cls: "is-missing" },
};

function metricHtml(key, value, suffix, reasonOverride, status) {
  const unknown = value == null;
  // 값이 없으면 왜 없는지, 있으면 그게 무엇인지 — 어느 쪽이든 한 줄은 붙는다.
  const text = unknown ? (reasonOverride || UNKNOWN_REASON[key]) : (METRIC_HINT[key] || "");
  const line = text ? '<div class="metric-reason">' + esc(text) + "</div>" : "";
  const scope = METRIC_SCOPE[key] || "";
  const badge = status && RATE_STATUS[status]
    ? '<span class="rate-tag ' + RATE_STATUS[status].cls + '">' +
        esc(RATE_STATUS[status].label) + "</span>"
    : "";
  // '추정'은 수치가 없지만 아는 게 있다 — 확인 불가로 적으면 거짓말이 된다.
  const display = status === "추정" ? "남은 자리 없음" : formatNumber(value, suffix);
  return (
    '<div class="metric' + (unknown ? " is-unknown" : "") +
        (status === "추정" ? " is-inferred" : "") + '">' +
      '<div class="key"' + (scope ? ' title="' + esc(scope) + '"' : "") + ">" +
        esc(key) +
        // 스코프는 툴팁만으로 두면 안 읽힌다 — 이 칸이 무엇의 값인지가
        // 카드에서 가장 자주 오해받는 지점이라 항상 보이게 적는다.
        (scope ? '<span class="metric-scope">이 지구 기준</span>' : "") +
        badge +
      "</div>" +
      '<div class="value">' + esc(display) + "</div>" +
      line +
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
  const status = card.sale_rate_status || "미상";
  const metrics = [
    { key: "분양율", value: card.sale_rate, suffix: "%",
      reason: status === "추정"
        // '추정'은 값 자리에 이미 판정이 들어가므로, 사유에는 그 판정의
        // 근거를 적는다 (같은 말을 두 번 하지 않는다).
        ? "원천 수치는 없지만 이미 입주가 끝난 단계입니다"
        : unknownRateReason(card),
      status },
    { key: "계획세대수", value: card.planned_households, suffix: "세대" },
  ];
  // '추정'은 값이 null이어도 화면에 내용이 있으므로 앞줄에 둔다
  const rank = (m) => (m.value != null ? 0 : m.status === "추정" ? 1 : 2);
  return metrics
    .slice()
    .sort((a, b) => rank(a) - rank(b))
    .map((m) => metricHtml(m.key, m.value, m.suffix, m.reason, m.status))
    .join("");
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

/** 마을 현황 블록 — 인구·고령화율·빈집 + 마을 소개.
 *
 * 전에는 "인구 131명 · 빈집 0호" 한 줄이 전부였다. 마을현황 API는 32개 필드를
 * 주는데 인덱스가 8개만 싣고 있었고, 그중 연령 16칸은 더해서 인구 하나로
 * 뭉갠 뒤 버렸다 — 그래서 봉산(61명 중 55명이 65세 이상)과 교원4리(505명 중 5%)가
 * 화면에서 똑같이 "인구 N명"으로 보였다. 귀농을 준비하는 사람에게 그 둘은
 * 완전히 다른 마을이다.
 *
 * 이 블록의 값은 전부 마을 것이지 지구 것이 아니다 — 그 경계를 매번 적는다.
 */
function villageBlockHtml(card) {
  const stats = [];
  if (card.population != null) stats.push("인구 " + esc(formatNumber(card.population, "명")));
  if (card.elderly_ratio != null) {
    const detail = card.elderly_count != null
      ? card.population + "명 중 " + card.elderly_count + "명"
      : "";
    stats.push(
      '<span class="elderly" title="' + esc(detail) + '">65세 이상 ' +
      esc(String(card.elderly_ratio)) + "%</span>"
    );
  }
  // 빈집은 **세 상태를 구분해서** 적는다.
  //
  // 🔴 직전 판은 "0은 변별력이 없다"며 아예 숨겼다. 점수에서 빼는 판단은
  // 맞았지만(127곳 중 65곳이 0이라 순위를 못 가른다) **화면에서 침묵시킨 것은
  // 틀렸다** — 조사돼서 0인 곳과 아예 조사가 안 된 곳이 똑같이 안 보였다.
  // "여기 빈집이 있는 곳인지 확실하냐"는 질문이 바로 여기서 나왔다.
  // 모르는 것을 모른다고 적는 게 이 서비스의 전부인데, 아는 것까지 지웠다.
  //
  // 🔴 라벨은 반드시 "마을 빈집"이다. 그냥 "빈집"으로 두면 **분양받아 들어갈
  // 집**으로 읽힌다 — 실제로 "빈집이 없는데 왜 추천하냐"는 질문이 나왔다.
  // 전원마을은 새 택지를 조성해 분양하는 사업이라 들어가는 집은 계획세대수
  // 쪽이고, 이 값은 옆 마을에 방치된 집의 수(마을 쇠퇴 지표)다.
  if (card.vacant_houses) {
    stats.push("마을 빈집 " + esc(formatNumber(card.vacant_houses, "호")));
  } else if (card.vacant_houses === 0) {
    stats.push("마을 빈집 없음");
  } else if (card.village_name) {
    // 마을은 붙었는데 빈집만 비어 있는 경우 (마을 자체가 안 붙으면 아래 안내가 담당)
    stats.push('<span class="stat-unknown">마을 빈집 미조사</span>');
  }
  // 🔴 슬레이트 주택은 카드에서 뺐다. 석면 우려 신호로 넣었지만 "2채"라는
  // 숫자만으로는 그게 많은지 적은지 알 수 없고(총주택 대비 중앙값 17%),
  // 값이 있는 곳도 36/127뿐이라 대부분의 카드에서 침묵한다. 무엇보다
  // **내가 들어갈 집이 슬레이트인지**를 말해 주지 않는다. 근거 패널과
  // 데이터 근거 페이지에는 그대로 남아 있다.

  const groupsOf = (obj) => (obj && typeof obj === "object"
    ? Object.entries(obj).filter(([, list]) => Array.isArray(list) && list.length)
    : []);
  const resources = groupsOf(card.village_resources);
  const resourceDetail = groupsOf(card.village_resources_detail);

  // 🔴 마을이 안 붙으면 카드 본문이 통째로 비었다. 배지에 "마을 상세 없음"이
  // 있긴 하지만 툴팁이라 안 읽히고, 사용자에게는 **그냥 아무것도 안 적힌 카드**로
  // 보인다("동박골은 왜 아무것도 안 적혀있어?"). 비어 있다는 사실보다
  // **왜 비었는지**가 정보다 — 우리가 뭘 못 했는지 그 자리에서 말한다.
  if (!stats.length && !card.village_note && !resources.length && !resourceDetail.length) {
    return (
      '<p class="village-missing">' +
        "<strong>마을 현황을 붙이지 못했습니다.</strong> " +
        "이 지구의 법정동코드와 일치하는 마을 기록이 농촌마을현황에 없어 " +
        "인구·고령화율·빈집을 표시할 수 없습니다 — 전국 167곳 중 16곳이 같습니다. " +
        "읍면동만 맞춰 다른 마을 수치를 가져다 붙이지는 않습니다." +
      "</p>"
    );
  }

  const head = stats.length
    ? '<p class="village-summary">' +
        "<strong>주변 마을" + (card.village_name ? " " + esc(card.village_name) : "") + "</strong> · " +
        stats.join(" · ") +
        // "무엇의 값인가"만 적고 "그래서 뭔데"를 안 적었더니, 마을 빈집이
        // 분양받을 집으로 읽혔다. 분양 대상이 어느 쪽인지 여기서 못박는다.
        '<span class="village-note">이 지구가 아니라 <strong>옆에 있는 기존 마을</strong>의 현황입니다. ' +
          "<strong>분양 대상이 아니며</strong> 적합도 점수에도 반영하지 않습니다 — " +
          "실제로 분양받는 것은 위의 계획세대수입니다.</span>" +
      "</p>"
    : "";

  // 긴 소개글은 접어 둔다. 잘라내는 게 아니라 접는 것이라 원문은 그대로 있다 —
  // 한 카드의 소개글이 길다고 나머지 카드 아래가 빈 공간이 되면 안 된다.
  const LONG = 150;
  const note = card.village_note
    ? '<figure class="village-desc' + (card.village_note.length > LONG ? " is-long" : "") + '">' +
        "<blockquote>" + esc(card.village_note) +
          (card.village_note_truncated ? '<span class="clip">… (원문 일부)</span>' : "") +
        "</blockquote>" +
        (card.village_note.length > LONG
          ? '<button class="desc-toggle" type="button" aria-expanded="false">더 보기</button>'
          : "") +
        "<figcaption>농촌마을현황 " + esc(card.village_name || "") +
          " 소개 원문 · villDescription</figcaption>" +
      "</figure>"
    : "";

  // 자원은 127곳 중 17곳만 등록돼 있다. 그래서 있는 곳에만 붙이고 점수에는
  // 넣지 않는다 — 13%만 판정할 수 있는 조건을 점수화하면 나머지 110곳이
  // "자원이 없는 마을"로 깎인다. 미등록과 부재는 다르다.
  const groupHtml = (pairs) => pairs.map(([group, list]) =>
    '<div class="res-group">' +
      '<span class="res-label">' + esc(group) + "</span>" +
      "<ul>" + list.map((t) => "<li>" + esc(t) + "</li>").join("") + "</ul>" +
    "</div>").join("");

  // 통계표를 그대로 부은 항목(토양·암석 수치)은 접는다. 지우지는 않는다 —
  // 원문을 감추면 "근거 있는 사실 확인"이 아니게 된다. 접기 전 이 마을들은
  // 카드가 1,400px를 넘었다(앙성 실측).
  const detailCount = resourceDetail.reduce((n, [, list]) => n + list.length, 0);
  const res = resources.length || detailCount
    ? '<div class="village-res">' +
        groupHtml(resources) +
        // 🔴 라벨을 "통계 원문 N건"이라고 쓰면 안 된다 — 접힌 것에는 통계뿐
        // 아니라 개수 상한을 넘긴 일반 항목도 섞여 있다. 실제로 첫 판이
        // 그렇게 적어 놓고 8건 중 6건이 일반 항목이었다. 중립적으로 센다.
        (detailCount
          ? '<details class="res-detail"><summary>자원 원문 ' + detailCount +
              "건 더 보기</summary>" + groupHtml(resourceDetail) + "</details>"
          : "") +
        '<p class="res-source">한국농어촌공사 마을 자원정보 원문 · resourceVill' +
        " <span>등록된 마을에만 표시하며 적합도 점수에는 넣지 않습니다." +
        (detailCount ? " 토양·암석 통계와 그 밖의 항목은 접어 두었고, 펼치면 원문 그대로 나옵니다." : "") +
        "</span></p>" +
      "</div>"
    : "";

  return head + note + res;
}

/** 카드에서 바로 갈 수 있는 다음 행동.
 *
 * 🔴 이게 없어서 카드가 막다른 길이었다. 지도·데이터셋 링크가 전부
 * `근거 · 위치 확인` 모달 안에만 있어서, 카드만 읽은 사람은 읽고 끝났다.
 * 사용자가 "정보가 적다"고 느끼는 지점은 필드 수가 아니라 여기라고 본다.
 *
 * 시군구청은 **검색 링크**로 건다 — 지자체마다 도메인이 달라 정확한 주소를
 * 알 수 없다. 모르는 URL을 지어내느니 검색을 여는 편이 정직하다.
 */
function cardActionsHtml(card, index) {
  const address = [card.sido, card.sigungu, card.eupmyeon].filter(Boolean).join(" ");
  const mapQuery = encodeURIComponent([address, card.gu_name].filter(Boolean).join(" "));
  const office = card.sigungu ? card.sigungu.replace(/[군시구]$/, (m) => m) + "청" : "";
  const officeQuery = encodeURIComponent(office + " 전원마을 분양 문의");

  return (
    '<div class="card-actions">' +
      '<button class="evidence-button" type="button" data-gu="' + esc(card.gu_name) +
        '" data-index="' + index + '">' + icon("fileSearch") + "근거 확인</button>" +
      '<a class="action-link" href="https://map.kakao.com/link/search/' + mapQuery +
        '" target="_blank" rel="noopener noreferrer">지도에서 보기</a>' +
      (office
        ? '<a class="action-link" href="https://www.google.com/search?q=' + officeQuery +
          '" target="_blank" rel="noopener noreferrer">' + esc(office) + " 문의처 찾기</a>"
        : "") +
      '<p class="action-note">분양가·남은 자리·신청 일정은 공공데이터에 없습니다 — ' +
        "실제 조건은 " + esc(office || "관할 시군구청") + "과 공식 분양처에서 확인하세요.</p>" +
    "</div>"
  );
}

function cardHtml(card, drought, index, terms) {
  const grade = String(card.confidence_grade || "D").toUpperCase();
  const badge = gradeText(grade);
  const score = Math.round(clamp(Number(card.score) || 0, 0, 1) * 100);
  const titleId = "result-title-" + index;
  // 카드 위쪽 배지에 이미 "분양중"이 있는데 선정 이유에 "진행단계=분양중"이
  // 또 나왔다. 같은 사실을 두 번 적으면 카드가 길어지기만 하고 읽히지 않는다.
  // 응답(reasons)은 손대지 않고 화면에서만 겹치는 항목을 뺀다.
  const shown = (Array.isArray(card.reasons) ? card.reasons : [])
    .filter((r) => !(card.sale_stage && r === "진행단계=" + card.sale_stage));
  const reasons = shown.map((reason) => "<li>" + esc(reason) + "</li>").join("");

  return (
    '<article class="result-card" aria-labelledby="' + titleId + '">' +
      '<div class="card-top">' +
        "<div>" +
          '<span class="rank">추천 ' + String(index + 1).padStart(2, "0") + "</span>" +
          '<h3 id="' + titleId + '">' + esc(card.gu_name) + "</h3>" +
          '<p class="location">' + esc([card.sido, card.sigungu, card.eupmyeon].filter(Boolean).join(" ")) + "</p>" +
        "</div>" +
        '<div class="badges">' +
          // 🔴 원천 라벨을 함께 적는다. '분양중'은 원천에서 **주택건축 단계**,
          // 즉 집을 짓고 있는 중이다. 우리 라벨만 두면 "지금 들어가 살 수 있다"로
          // 읽히는데 그런 뜻이 아니다.
          '<span class="badge stage"' +
            (card.sale_stage_source
              ? ' title="원천 기록: ' + esc(card.sale_stage_source) + '"' : "") + ">" +
            esc(card.sale_stage || "단계 확인 불가") +
            (card.sale_stage_source && card.sale_stage_source !== card.sale_stage
              ? '<span class="badge-source">' + esc(card.sale_stage_source) + "</span>"
              : "") +
          "</span>" +
          '<span class="badge ' + gradeClass(grade) + '" title="' + esc(badge.title) + '">' +
            esc(badge.label) + "</span>" +
        "</div>" +
      "</div>" +
      '<div class="metrics">' + metricsHtml(card) + "</div>" +
      // 단계와 수치가 어긋나는 조합(분양예정인데 100% — 전국 12건).
      // 값을 지우지도 고치지도 않고 어긋난다는 사실만 알린다.
      (card.sale_rate_anomaly
        ? '<p class="rate-anomaly">' + esc(card.sale_rate_anomaly) +
          " — 실제 입주 가능 여부는 분양처 확인이 필요합니다.</p>"
        : "") +
      // 값이 하나도 없으면 블록 자체를 내지 않는다 ("확인 불가 · 확인 불가"는 정보가 아니라 노이즈)
      villageBlockHtml(card) +
      (reasons ? '<ul class="reasons" aria-label="선정 이유">' + reasons + "</ul>" : "") +
      '<div class="score-row"><span>조건 적합도</span><strong>' + score + "%</strong></div>" +
      '<div class="score-bar" role="progressbar" aria-label="조건 적합도" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + score + '">' +
        '<div class="score-fill" style="width:' + score + '%"></div>' +
      "</div>" +
      scoreFormula(terms) +
      droughtHtml(drought && drought.sigungu === card.sigungu ? drought : null) +
      cardActionsHtml(card, index) +
    "</article>"
  );
}

function resetResultsHeading(title) {
  el.resultsTitle.textContent = title;
  el.resultsLead.textContent = "";
  if (el.seeAll) el.seeAll.hidden = true;
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
/** 전체 목록 페이지로 넘길 검색 조건.
 *
 * 화면에서 읽어 URL 쿼리로 만든다 — 새로고침·공유가 되어야 하므로
 * sessionStorage가 아니라 주소에 싣는다.
 */
function allResultsQuery() {
  const params = new URLSearchParams();
  const query = el.query.value.trim();
  if (query) params.set("q", query);
  if (el.selSido.value) params.set("sido", el.selSido.value);
  if (el.selSigungu.value) params.set("sigungu", el.selSigungu.value);
  if (el.selStage.value) params.set("stage", el.selStage.value);
  return params.toString();
}

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

  // 🔴 "조건 충족 56곳 · 상위 3곳 표시"라고 적어 놓고 나머지 53곳을 볼 방법이
  // 없었다. 계산을 공개한다면서 결과의 대부분을 감춘 셈이다.
  if (el.seeAll) {
    const hidden = matched != null && matched > shown;
    el.seeAll.hidden = !hidden;
    if (hidden) {
      el.seeAll.textContent = "조건 충족 " + matched + "곳 전체 보기";
      el.seeAll.href = "/all-results.html?" + allResultsQuery();
    }
  }

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

/** 원본 데이터셋 — data.go.kr 공개 페이지 (링크 유효성 실측 확인).
 *  evidence의 api 필드값(숫자 ID)을 그대로 키로 쓴다. */
const DATASET_PAGE = {
  15104395: { name: "전원마을 분양정보", url: "https://www.data.go.kr/data/15104395/openapi.do" },
  15104291: { name: "농촌마을현황", url: "https://www.data.go.kr/data/15104291/openapi.do" },
  15117185: { name: "논가뭄지도", url: "https://www.data.go.kr/data/15117185/fileData.do" },
};

/** "이 지구를 더 알아보려면" 블록.
 *
 * 공공데이터가 주는 항목은 카드에 이미 다 나와 있어 모달에 더 보여줄 수치가
 * 없다. 없는 상세를 지어내는 대신 **어디서 확인하는지**를 준다 — 위치는 지도,
 * 수치의 출처는 원본 데이터셋, 분양가·면적·일정은 공식 분양처.
 */
function nextStepsHtml(card, apis) {
  if (!card) return "";
  const address = [card.sido, card.sigungu, card.eupmyeon].filter(Boolean).join(" ");
  const mapQuery = encodeURIComponent([address, card.gu_name].filter(Boolean).join(" "));
  const datasets = [...new Set(apis)]
    .map((id) => DATASET_PAGE[id])
    .filter(Boolean)
    .map((d) => '<li><a href="' + d.url + '" target="_blank" rel="noopener noreferrer">' +
                esc(d.name) + " 원본 데이터셋</a></li>")
    .join("");

  return (
    '<div class="modal-next">' +
      "<h3>이 지구를 더 알아보려면</h3>" +
      "<ul>" +
        '<li><a href="https://map.kakao.com/link/search/' + mapQuery +
          '" target="_blank" rel="noopener noreferrer">지도에서 위치 보기</a>' +
          '<span class="modal-next-note">' + esc(address || "주소 정보 없음") + "</span></li>" +
        datasets +
      "</ul>" +
      '<p class="modal-next-limit">공공데이터로 확인할 수 있는 항목은 위 표가 전부입니다 — ' +
        "<strong>분양가·대지면적·신청 일정·연락처는 제공되지 않습니다</strong>. " +
        "실제 분양 조건은 관할 시군구청과 공식 분양처에서 확인해 주세요.</p>" +
    "</div>"
  );
}

function openEvidence(guName, card) {
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
    nextStepsHtml(card, rows.map((r) => r.api)) +
    '<div class="modal-disclaimer">' + esc(lastDisclaimer) + "</div>"
  );
  el.modal.showModal();
}

// --- 지역 드롭다운 (자연어 입력의 대안 경로) ---

/** 선택된 값들. 문장 없이 이것만 있으면 그대로 조건이 되고,
 *  문장과 함께 있으면 문장 해석 결과 중 이 항목들만 덮어쓴다.
 */
function selectedFilters() {
  const sido = el.selSido.value;
  const sigungu = el.selSigungu.value;
  const stage = el.selStage.value;
  if (!sido && !sigungu && !stage) return null;
  return { sido: sido || null, sigungu: sigungu || null, sale_stage: stage || null };
}

/** 목록 선택만 있을 때 쓰는 백엔드 ParsedQuery.
 *
 * 문장으로 바꿔 파서에 다시 태우지 않는 이유: 사용자가 목록에서 직접 고른
 * 값은 이미 확정된 조건이다. 그걸 다시 문장으로 만들어 해석시키면 추측이
 * 한 단계 끼어든다 — 실제로 "예산"을 시군구와 예산(금액)으로 동시에 읽어
 * 결과가 0건이 된 적이 있다. 서버의 structured 경로가 파싱을 건너뛴다.
 */
function structuredFromSelects() {
  const f = selectedFilters();
  if (!f) return null;
  return {
    region: { sido: f.sido, sigungu: f.sigungu },
    budget_max_krw: null,
    sale_stage: f.sale_stage ? [f.sale_stage] : [],
    household_min: null,
    preferences: [],
    confidence: 1,                    // 해석한 값이 아니라 사용자가 고른 값
    raw: [f.sido, f.sigungu, f.sale_stage].filter(Boolean).join(" "),
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
    // 전국 17개 시도가 아니라 분양 지구가 실재하는 곳만 나온다. 그 사실을
    // 밝히지 않으면 "경기도가 없는데 고장인가"로 읽힌다 (실제로 그 질문이 나왔다).
    el.regionHint.textContent =
      "전원마을 분양 지구가 있는 " + data.시도.length + "개 시도만 표시됩니다";
    el.regionHint.hidden = false;
    el.regionFilter.hidden = false;
  } catch (error) {
    // 지역 선택은 보조 수단 — 실패하면 조용히 숨긴 채로 두고 자연어 검색을 남긴다
  }
}

async function runSearch() {
  // 세 갈래: 문장만 / 목록만 / 둘 다.
  //   문장만  → 서버가 문장을 해석
  //   목록만  → structured (해석 단계 자체를 건너뜀)
  //   둘 다   → 문장을 해석하되 지역·단계는 고른 값으로 덮어씀 (filters)
  const filters = selectedFilters();
  const query = el.query.value.trim();
  const structured = query ? null : structuredFromSelects();
  if (!filters && !query) {
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
    if (!structured && filters) payload.filters = filters;
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
    lastCards = Array.isArray(data.top) ? data.top : [];
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
  }
});

// 드롭다운은 조건을 '고르는' 곳이지 검색을 '실행하는' 곳이 아니다.
// 고를 때마다 검색이 나가면 시도→시군구→단계를 순서대로 좁히는 동안 세 번
// 검색되고, 문장을 함께 쓰려던 사용자는 입력을 마치기도 전에 결과를 본다.
// 실행은 '마을 찾기' 한 곳으로 모은다.
el.selSido.addEventListener("change", () => {
  fillSigungu(el.selSido.value);
  el.queryError.hidden = true;
  syncRegionReset();
});

el.selSigungu.addEventListener("change", syncRegionReset);

el.selStage.addEventListener("change", () => {
  el.queryError.hidden = true;
  syncRegionReset();
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
    openEvidence(evidenceButton.dataset.gu || "선택한 마을",
                 lastCards[Number(evidenceButton.dataset.index)]);
    return;
  }

  // 소개글 접기/펼치기 — 마을마다 길이가 크게 달라(최장 400자) 그대로 두면
  // 한 카드가 나머지를 밀어내고 짧은 카드 아래에 빈 공간이 크게 남는다.
  // 자르는 대신 접는다 — 원문은 클릭 한 번이면 전부 보인다.
  const descToggle = event.target.closest(".desc-toggle");
  if (descToggle) {
    const figure = descToggle.closest(".village-desc");
    const open = figure.classList.toggle("is-open");
    descToggle.textContent = open ? "접기" : "더 보기";
    descToggle.setAttribute("aria-expanded", String(open));
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
