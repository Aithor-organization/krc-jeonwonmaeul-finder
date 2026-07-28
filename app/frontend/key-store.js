"use strict";

/* LLM API 키 보관소 — 검색 화면과 설정 화면이 같은 규칙을 쓰도록 한 곳에 둔다.
   두 화면이 각자 저장 키 이름을 들고 있으면 한쪽만 고쳐질 때 조용히 어긋난다. */
window.KrcKeyStore = (function () {
  // sessionStorage인 이유: 탭을 닫으면 사라진다. localStorage는 로그아웃 개념이
  // 없는 정적 페이지에서 남의 브라우저에 키를 무기한 남긴다.
  const STORE_KEY = "krc.openai_key";

  function read() {
    try {
      return window.sessionStorage.getItem(STORE_KEY) || "";
    } catch (_error) {
      return "";   // 프라이빗 모드 등 storage 차단 환경
    }
  }

  function write(value) {
    const key = (value || "").trim();
    try {
      if (key) window.sessionStorage.setItem(STORE_KEY, key);
      else window.sessionStorage.removeItem(STORE_KEY);
    } catch (_error) {
      /* storage 불가여도 이번 화면 입력값은 그대로 쓴다 */
    }
    return key;
  }

  /* 형식만 본다 — 유효성은 실제 호출로만 알 수 있다(설정 화면의 "키 확인"). */
  function looksLikeKey(value) {
    return /^sk-[A-Za-z0-9_-]{16,}$/.test((value || "").trim());
  }

  /* 화면에 되비출 때 쓰는 마스킹. 원문을 그대로 다시 그리지 않는다. */
  function mask(value) {
    const key = (value || "").trim();
    if (key.length <= 10) return key ? "sk-***" : "";
    return key.slice(0, 6) + "…" + key.slice(-4);
  }

  return { read, write, looksLikeKey, mask };
})();
