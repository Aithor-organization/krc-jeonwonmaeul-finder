"""설정 — sample-mode, allowlist, 상수. 키가 없으면 자동 sample-mode."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = BASE_DIR / "data" / "samples"
FRONTEND_DIR = BASE_DIR.parent / "frontend"

# 공공데이터포털 서비스키. 없으면 sample-mode(오프라인 샘플)로 동작.
KRC_SERVICE_KEY: str | None = os.environ.get("KRC_SERVICE_KEY") or None
LIVE_KEY_PRESENT: bool = KRC_SERVICE_KEY is not None
# 키가 있으면 live-mode. 실호출 실패 시 clients.py가 샘플로 fallback하며 경고를 남긴다.
# (2026-07-27 live 경로 구현 완료 — 기술명세 §14 "오퍼레이션명 미확정" 해소)
SAMPLE_MODE: bool = not LIVE_KEY_PRESENT

# SSRF 방어 — 외부 호출 허용 호스트 (기술명세 §6.2)
ALLOWLIST_HOSTS: frozenset[str] = frozenset({"apis.data.go.kr", "api.data.go.kr"})

# KRC OpenAPI 데이터셋 ID (기술명세 §3.1)
API_SALE = "15104395"       # 전원마을 분양정보 (핵심)
API_VILLAGE = "15104291"    # 농촌마을현황 (보조)
API_DROUGHT = "15117185"    # 논가뭄지도 (지역 가뭄 패널)
API_RESERVOIR = "15099919"  # 저수지 수위정보 (선택)

HTTP_TIMEOUT_S = 5.0

DISCLAIMER = "공공데이터 기반 참고정보이며 최종 계약·분양은 공식 기관 확인이 필요합니다."

# --- LLM 자연어 파서 모델 라우팅 (선택, 기술명세 §4.2 Option A) ---
# 키는 코드/커밋에 두지 않고 파일에서 런타임 로드. USE_LLM=1일 때만 활성(기본 결정론 파서).
OPENAI_KEY_FILE = os.environ.get("OPENAI_KEY_FILE", "/home/cafe99/workspace/키저장.md")
OPENAI_KEY_ENV = os.environ.get("OPENAI_API_KEY") or None
LLM_ENABLED: bool = os.environ.get("USE_LLM", "").lower() in ("1", "true", "yes")
LLM_MODEL_SIMPLE = os.environ.get("LLM_MODEL_SIMPLE", "gpt-5.4-nano")
LLM_MODEL_MEDIUM = os.environ.get("LLM_MODEL_MEDIUM", "gpt-5.4-mini")
LLM_MODEL_COMPLEX = os.environ.get("LLM_MODEL_COMPLEX", "gpt-5.6-luna")
LLM_TIMEOUT_S = float(os.environ.get("LLM_TIMEOUT_S", "20"))

# 가뭄단계 기준 (논가뭄지도 실측: 평년대비 임계)
def drought_stage_from_ratio(normal_ratio: float | None) -> str:
    if normal_ratio is None:
        return "확인 불가"
    if normal_ratio <= 40:
        return "심각"
    if normal_ratio <= 50:
        return "경계"
    if normal_ratio <= 60:
        return "주의"
    if normal_ratio <= 70:
        return "관심"
    return "정상"
