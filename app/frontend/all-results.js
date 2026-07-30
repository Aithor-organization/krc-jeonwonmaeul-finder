"use strict";

/** 조건을 충족한 전체 목록.
 *
 * 홈 화면은 상위 3곳만 보여 준다. 퍼널에 "탈락 N건"이라고 적어 두긴 했지만
 * 그 N건이 무엇인지는 볼 방법이 없었다 — 계산을 공개한다면서 결과의 대부분을
 * 감추고 있었던 셈이다. 이 페이지가 그걸 연다.
 *
 * 검색 조건은 URL 쿼리로 받는다(공유·새로고침이 가능해야 한다).
 *   ?q=충청북도 분양중            자연어 문장
 *   ?sido=충청북도&stage=분양중    드롭다운 선택
 */

const esc = (value) => String(value == null ? "" : value)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

const numberFormatter = new Intl.NumberFormat("ko-KR");

function formatNumber(value, suffix = "") {
  if (value == null || value === "") return "확인 불가";
  const number = Number(value);
  return Number.isFinite(number) ? numberFormatter.format(number) + suffix : "확인 불가";
}

/** 홈 카드와 같은 규칙 — '추정'은 수치가 없어도 아는 것이 있다. */
function rateCell(card) {
  if (card.sale_rate != null) return esc(formatNumber(card.sale_rate, "%"));
  if (card.sale_rate_status === "추정") return "남은 자리 없음";
  if (card.sale_rate_out_of_range != null) {
    return "확인 불가 <small>원천 " + esc(String(card.sale_rate_out_of_range)) + "%</small>";
  }
  return "확인 불가";
}

function villageCell(card) {
  if (!card.village_name) return "<small>결합된 마을 없음</small>";
  const bits = [];
  if (card.population != null) bits.push("인구 " + formatNumber(card.population));
  if (card.elderly_ratio != null) bits.push("65세+ " + card.elderly_ratio + "%");
  if (card.vacant_houses) bits.push("빈집 " + card.vacant_houses);
  return esc(card.village_name) + (bits.length ? " <small>" + esc(bits.join(" · ")) + "</small>" : "");
}

function rowHtml(card, index) {
  const score = Math.round(Math.max(0, Math.min(1, Number(card.score) || 0)) * 100);
  const region = [card.sido, card.sigungu, card.eupmyeon].filter(Boolean).join(" ");
  return (
    "<tr>" +
      "<td>" + (index + 1) + "</td>" +
      "<td><strong>" + esc(card.gu_name) + "</strong></td>" +
      "<td>" + esc(region) + "</td>" +
      "<td>" + esc(card.sale_stage || "확인 불가") +
        (card.sale_stage_source && card.sale_stage_source !== card.sale_stage
          ? " <small>" + esc(card.sale_stage_source) + "</small>" : "") +
      "</td>" +
      '<td class="r">' + esc(formatNumber(card.planned_households, "세대")) + "</td>" +
      "<td>" + rateCell(card) + "</td>" +
      "<td>" + villageCell(card) + "</td>" +
      '<td class="r"><strong>' + score + "%</strong></td>" +
    "</tr>"
  );
}

/** URL 쿼리 → /api/search 요청 본문.
 *
 * 홈과 같은 규칙을 따른다 — 문장이 있으면 문장으로, 없으면 드롭다운 값으로.
 * 문장과 드롭다운이 함께 오면 드롭다운이 지역·단계를 덮어쓴다.
 */
function payloadFromUrl(params) {
  const query = (params.get("q") || "").trim();
  const sido = params.get("sido") || null;
  const sigungu = params.get("sigungu") || null;
  const stage = params.get("stage") || null;
  const hasFilters = Boolean(sido || sigungu || stage);

  // 상한 167 = 원천 지구 전체. 그 이상은 존재하지 않는다.
  const payload = { top_n: 167 };
  if (query) {
    payload.query = query;
    if (hasFilters) payload.filters = { sido, sigungu, sale_stage: stage };
  } else if (hasFilters) {
    payload.structured = {
      region: { sido, sigungu },
      sale_stage: stage ? [stage] : [],
      preferences: [],
      confidence: 1,
      raw: [sido, sigungu, stage].filter(Boolean).join(" "),
    };
  } else {
    payload.query = "";
  }
  return payload;
}

function describeCondition(params) {
  const bits = [];
  const query = (params.get("q") || "").trim();
  if (query) bits.push("문장 “" + query + "”");
  const region = [params.get("sido"), params.get("sigungu")].filter(Boolean).join(" ");
  if (region) bits.push(region);
  if (params.get("stage")) bits.push(params.get("stage"));
  return bits.length ? bits.join(" · ") : "조건 없음 (전국)";
}

async function load() {
  const body = document.querySelector("#all-body");
  const lead = document.querySelector("#all-lead");
  const note = document.querySelector("#all-note");
  const params = new URLSearchParams(location.search);
  lead.textContent = describeCondition(params) + " — 불러오는 중…";

  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payloadFromUrl(params)),
    });
    if (!response.ok) throw new Error("HTTP " + response.status);
    const data = await response.json();
    const cards = Array.isArray(data.top) ? data.top : [];

    if (!cards.length) {
      body.innerHTML = '<tr><td colspan="8">조건에 맞는 전원마을을 찾지 못했습니다.</td></tr>';
      lead.textContent = describeCondition(params) + " — 0곳";
      return;
    }

    body.innerHTML = cards.map(rowHtml).join("");
    const funnel = (data.trace && Array.isArray(data.trace.funnel)) ? data.trace.funnel : [];
    const total = funnel.length ? funnel[0].count : null;
    lead.textContent = describeCondition(params) + " — " + cards.length + "곳"
      + (total != null ? " (전국 " + total + "곳 중)" : "");

    // 어떻게 줄었는지도 같이 적는다 — 목록만 주고 과정을 감추면 홈과 같은 문제다.
    if (funnel.length) {
      note.innerHTML = "<strong>이 목록이 나온 과정:</strong> " +
        funnel.slice(0, -1)
          .map((step) => esc(step.label) + " " + step.count + "곳"
                         + (step.dropped ? " (탈락 " + step.dropped + ")" : ""))
          .join(" → ") +
        ". 홈 화면은 이 중 상위 3곳만 보여 줍니다.";
    }
  } catch (error) {
    body.innerHTML = '<tr><td colspan="8">결과를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</td></tr>';
    lead.textContent = describeCondition(params) + " — 불러오기 실패";
  }
}

load();
