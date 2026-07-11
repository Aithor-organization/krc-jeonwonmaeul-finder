"""Input/Output Guard — PII 마스킹, prompt injection 차단, SSRF allowlist (기술명세 §6)."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from config import ALLOWLIST_HOSTS

_RRN = re.compile(r"\d{6}[-. ]?\d{7}")                        # 주민등록번호
_PHONE = re.compile(r"01[016789][-. ]?\d{3,4}[-. ]?\d{4}")    # 휴대폰(-, ., 공백 구분)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

_INJECTION = [
    re.compile(r"이전\s*(지시|명령|프롬프트).*(무시|무효)"),
    re.compile(r"(시스템|system)\s*(프롬프트|prompt)", re.IGNORECASE),
    re.compile(r"ignore\s+(the\s+)?(previous|above|prior|all)", re.IGNORECASE),
    re.compile(r"disregard\s+(all|previous|the)", re.IGNORECASE),
    re.compile(r"프롬프트를?\s*(무시|잊)", ),
]


def inspect_input(text: str | None) -> tuple[str, bool, list[str]]:
    """반환: (정제된 텍스트, blocked, 사유들). PII는 마스킹, injection은 차단."""
    if not text:
        return "", False, []
    reasons: list[str] = []
    cleaned = text

    # 개행/다중공백을 정규화한 뒤 injection 검사 (개행 우회 방지)
    norm = re.sub(r"\s+", " ", text)
    for pat in _INJECTION:
        if pat.search(norm):
            return cleaned, True, ["prompt injection 의심 패턴 감지 — 요청 차단"]

    if _RRN.search(cleaned):
        cleaned = _RRN.sub("[삭제된 식별정보]", cleaned)
        reasons.append("주민등록번호 마스킹")
    if _PHONE.search(cleaned):
        cleaned = _PHONE.sub("[삭제된 연락처]", cleaned)
        reasons.append("연락처 마스킹")
    if _EMAIL.search(cleaned):
        cleaned = _EMAIL.sub("[삭제된 이메일]", cleaned)
        reasons.append("이메일 마스킹")

    return cleaned, False, reasons


def inspect_output(text: str) -> str:
    """출력에서 유출 가능한 식별정보 리댁션."""
    if not text:
        return text
    text = _RRN.sub("[삭제]", text)
    text = _PHONE.sub("[삭제]", text)
    return text


def is_allowed_host(url: str) -> bool:
    """SSRF 방어 — KRC allowlist 호스트만 허용."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host in ALLOWLIST_HOSTS
