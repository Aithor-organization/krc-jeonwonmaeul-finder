"use strict";

/* 푸터 데이터 모드 표시 — HTML에 하드코딩돼 있어 실제 모드와 어긋나던 것을 실데이터로 갱신. */
(async function syncModeFlag() {
  const flag = document.querySelector(".mode-flag");
  if (!flag) return;
  try {
    const response = await fetch("/api/health", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("HTTP " + response.status);
    const health = await response.json();
    flag.textContent = health.sample_mode ? "sample-mode로 동작 중" : "공공데이터 연결 모드로 동작 중";
  } catch (_error) {
    flag.textContent = "데이터 상태 확인 불가";
  }
})();

/* FAQ accordion — single open at a time, keyboard + ARIA friendly. */
document.querySelectorAll(".faq-item").forEach((item) => {
  const button = item.querySelector(".faq-q");
  if (!button) return;
  button.setAttribute("aria-expanded", item.classList.contains("open") ? "true" : "false");
  button.addEventListener("click", () => {
    const willOpen = !item.classList.contains("open");
    document.querySelectorAll(".faq-item.open").forEach((open) => {
      open.classList.remove("open");
      const b = open.querySelector(".faq-q");
      if (b) {
        b.setAttribute("aria-expanded", "false");
        const s = b.querySelector(".sign");
        if (s) s.textContent = "+";
      }
    });
    if (willOpen) {
      item.classList.add("open");
      button.setAttribute("aria-expanded", "true");
      const sign = button.querySelector(".sign");
      if (sign) sign.textContent = "\u2212";
    }
  });
});
