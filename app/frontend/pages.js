"use strict";

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
