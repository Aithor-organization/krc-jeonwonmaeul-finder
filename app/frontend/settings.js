"use strict";

/* 설정 화면 — LLM API 키 입력·확인·삭제.
   저장 규칙 자체는 key-store.js가 단일 출처다 (검색 화면과 공유). */
(function () {
  const store = window.KrcKeyStore;
  const $ = (sel) => document.querySelector(sel);

  const form = $("#key-form");
  const input = $("#openai-key");
  const state = $("#key-state");
  const stateText = $("#key-state-text");
  const error = $("#key-error");
  const result = $("#key-result");
  const testButton = $("#key-test");
  const clearButton = $("#key-clear");
  if (!form || !store) return;

  function setError(message) {
    error.textContent = message || "";
    error.hidden = !message;
  }

  function setResult(message, kind) {
    result.textContent = message || "";
    result.hidden = !message;
    result.dataset.kind = kind || "";
  }

  /* 저장된 키는 입력란에 되돌려 넣지 않는다 — 원문을 DOM에 다시 띄울 이유가 없다.
     대신 마스킹된 상태만 보여주고, 교체하려면 새로 입력하게 한다. */
  function syncState() {
    const key = store.read();
    const has = Boolean(key);
    state.dataset.state = has ? "set" : "empty";
    stateText.textContent = has
      ? `키 저장됨 (${store.mask(key)}) — 이 탭에서만 사용`
      : "저장된 키 없음 — 규칙 파서로 동작 중";
    input.placeholder = has ? "새 키를 입력하면 교체됩니다" : "sk-...";
    testButton.disabled = !has;
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    setResult("");
    const value = input.value.trim();
    if (!value) {
      setError("키를 입력해 주세요. 저장된 키를 지우려면 삭제 버튼을 눌러 주세요.");
      return;
    }
    if (!store.looksLikeKey(value)) {
      // 형식만 거른다 — 실제 유효성은 "키 확인"이 호출로 판정한다.
      setError("OpenAI 키 형식이 아닙니다. sk- 로 시작하는 키를 붙여넣어 주세요.");
      return;
    }
    setError("");
    store.write(value);
    input.value = "";
    syncState();
    setResult("저장했습니다. 검색 화면에서 바로 사용됩니다.", "ok");
  });

  clearButton.addEventListener("click", () => {
    store.write("");
    input.value = "";
    setError("");
    syncState();
    setResult("삭제했습니다. 이제 규칙 파서로 동작합니다.", "ok");
  });

  input.addEventListener("input", () => setError(""));

  /* 실제로 되는 키인지는 호출해 봐야 안다. 검색 한 번을 보내고
     응답의 notes/warnings로 LLM 경로가 실제로 탔는지 판정한다. */
  testButton.addEventListener("click", async () => {
    const key = store.read();
    if (!key) return;
    testButton.disabled = true;
    setResult("확인 중…", "");
    try {
      const response = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: "충남 분양 중인 마을", openai_api_key: key }),
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const data = await response.json();

      const fallback = (data.warnings || []).find((w) => w.includes("LLM 파싱 폴백"));
      const model = (data.notes || []).find((n) => n.includes("자연어 파싱 모델"));
      if (fallback) {
        // 서버가 키를 마스킹한 상태로 사유만 돌려준다 (llm_intent.redact)
        setResult(`키가 동작하지 않았습니다 — ${fallback.replace("LLM 파싱 폴백(규칙 파서 사용): ", "")}`, "fail");
      } else if (model) {
        setResult(`정상 동작합니다 — ${model}`, "ok");
      } else {
        setResult("응답에서 파싱 경로를 확인하지 못했습니다.", "fail");
      }
    } catch (err) {
      setResult(`확인 실패: ${err.message}`, "fail");
    } finally {
      testButton.disabled = false;
    }
  });

  syncState();
})();
