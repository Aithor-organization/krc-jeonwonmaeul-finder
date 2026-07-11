"use strict";

const $ = (sel) => document.querySelector(sel);
const el = {
  query: $("#query"),
  searchBtn: $("#search-btn"),
  backBtn: $("#back-btn"),
  viewInput: $("#view-input"),
  viewResults: $("#view-results"),
  cards: $("#cards"),
  status: $("#status"),
  parsedInfo: $("#parsed-info"),
  modal: $("#modal"),
  modalBody: $("#modal-body"),
  modalClose: $("#modal-close"),
};

let lastEvidence = [];
let lastDisclaimer = "";

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function showView(which) {
  el.viewInput.classList.toggle("active", which === "input");
  el.viewInput.hidden = which !== "input";
  el.viewResults.classList.toggle("active", which === "results");
  el.viewResults.hidden = which !== "results";
}

function parsedSummary(p) {
  if (!p) return "";
  const parts = [];
  if (p.region && p.region.sido) parts.push(p.region.sido);
  if (p.budget_max_krw) parts.push("예산 " + (p.budget_max_krw / 100000000) + "억");
  if (p.sale_stage && p.sale_stage.length) parts.push(p.sale_stage.join("/"));
  if (p.preferences && p.preferences.length) parts.push(p.preferences.join(", "));
  return "해석된 조건: " + (parts.join(" · ") || "조건 미검출") + " (신뢰도 " + Math.round((p.confidence || 0) * 100) + "%)";
}

function droughtHtml(d) {
  if (!d) return "";
  return (
    '<div class="drought-panel">🌾 이 지역(' + esc(d.sigungu) + ') 농업가뭄단계: ' +
    '<span class="stage-' + esc(d.drought_stage) + '">' + esc(d.drought_stage) + "</span>" +
    (d.normal_ratio != null ? " (평년대비 " + esc(d.normal_ratio) + "%)" : "") +
    '<br><span class="note">출처: 논가뭄지도 · 기준일 ' + esc(d.base_date || "-") + " · " + esc(d.note || "") + " · 마을 점수에는 반영되지 않는 참고 정보</span></div>"
  );
}

function cardHtml(c, drought) {
  const grade = c.confidence_grade || "D";
  const reasons = (c.reasons || []).map((r) => "<li>" + esc(r) + "</li>").join("");
  return (
    '<article class="card">' +
    '<div class="card-top"><div><h3>' + esc(c.gu_name) + "</h3>" +
    '<div class="loc">' + esc(c.sido) + " " + esc(c.sigungu) + " " + esc(c.eupmyeon || "") + "</div></div>" +
    '<div class="badges"><span class="badge stage">' + esc(c.sale_stage || "-") + "</span>" +
    '<span class="badge grade-' + esc(grade) + '">신뢰도 ' + esc(grade) + "</span></div></div>" +
    '<div class="metrics">' +
    '<div class="metric"><div class="k">분양율</div><div class="v">' + esc(c.sale_rate != null ? c.sale_rate + "%" : "확인 불가") + "</div></div>" +
    '<div class="metric"><div class="k">계획세대수</div><div class="v">' + esc(c.planned_households != null ? c.planned_households : "-") + "</div></div>" +
    "</div>" +
    '<div class="village-sum">인구 ' + esc(c.population != null ? c.population : "확인 불가") + " · 빈집 " + esc(c.vacant_houses != null ? c.vacant_houses : "확인 불가") + "</div>" +
    (reasons ? '<ul class="reasons">' + reasons + "</ul>" : "") +
    '<div class="score-bar"><div class="score-fill" style="width:' + Math.round((c.score || 0) * 100) + '%"></div></div>' +
    droughtHtml(drought) +
    '<div class="card-actions"><button class="evi-btn" type="button" data-gu="' + esc(c.gu_name) + '">근거 보기</button></div>' +
    "</article>"
  );
}

function openEvidence(guName) {
  const rows = lastEvidence.filter((e) => e.claim && e.claim.indexOf("[" + guName + "]") === 0);
  const body =
    "<table><thead><tr><th>주장</th><th>API</th><th>필드</th><th>값</th></tr></thead><tbody>" +
    (rows.length
      ? rows.map((e) => "<tr><td>" + esc(e.claim) + "</td><td>" + esc(e.api) + "</td><td>" + esc(e.field) + "</td><td>" + esc(e.value) + "</td></tr>").join("")
      : '<tr><td colspan="4">확인 가능한 근거가 없습니다.</td></tr>') +
    "</tbody></table>" +
    '<div class="modal-disclaimer">' + esc(lastDisclaimer) + "</div>";
  el.modalBody.innerHTML = body;
  el.modal.hidden = false;
}

async function runSearch() {
  const q = el.query.value.trim();
  if (!q) {
    el.query.focus();
    return;
  }
  showView("results");
  el.status.className = "status";
  el.status.textContent = "검색 중…";
  el.cards.innerHTML = "";
  el.parsedInfo.textContent = "";
  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q }),
    });
    if (!res.ok) throw new Error("서버 오류 " + res.status);
    const data = await res.json();
    lastEvidence = data.evidence || [];
    lastDisclaimer = data.disclaimer || "";
    el.parsedInfo.textContent = parsedSummary(data.query_parsed);

    const warn = (data.warnings || []).filter(Boolean);
    if (!data.top || data.top.length === 0) {
      el.status.textContent = "조건에 맞는 결과가 없습니다. " + (warn.join(" ") || "다른 조건으로 시도해 보세요.");
      return;
    }
    el.status.textContent = warn.length ? "ⓘ " + warn.join(" ") : "";
    el.cards.innerHTML = data.top.map((c) => cardHtml(c, data.drought_panel)).join("");
    el.cards.querySelectorAll(".evi-btn").forEach((b) =>
      b.addEventListener("click", () => openEvidence(b.getAttribute("data-gu")))
    );
  } catch (err) {
    el.status.className = "status error";
    el.status.textContent = "검색에 실패했습니다: " + err.message;
  }
}

el.searchBtn.addEventListener("click", runSearch);
el.query.addEventListener("keydown", (e) => { if (e.key === "Enter") runSearch(); });
el.backBtn.addEventListener("click", () => showView("input"));
el.modalClose.addEventListener("click", () => (el.modal.hidden = true));
el.modal.addEventListener("click", (e) => { if (e.target === el.modal) el.modal.hidden = true; });
document.querySelectorAll(".chip").forEach((chip) =>
  chip.addEventListener("click", () => { el.query.value = chip.textContent; runSearch(); })
);
