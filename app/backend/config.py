"""설정 — sample-mode, allowlist, 상수. 키가 없으면 자동 sample-mode."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = BASE_DIR / "data" / "samples"
FRONTEND_DIR = BASE_DIR.parent / "frontend"

# 공공데이터포털 서비스키. 없으면 sample-mode(오프라인 샘플)로 동작.
KRC_SERVICE_KEY: str | None = os.environ.get("KRC_SERVICE_KEY") or None
SAMPLE_MODE: bool = KRC_SERVICE_KEY is None

# SSRF 방어 — 외부 호출 허용 호스트 (기술명세 §6.2)
ALLOWLIST_HOSTS: frozenset[str] = frozenset({"apis.data.go.kr", "api.data.go.kr"})

# KRC OpenAPI 데이터셋 ID (기술명세 §3.1)
API_SALE = "15104395"       # 전원마을 분양정보 (핵심)
API_VILLAGE = "15104291"    # 농촌마을현황 (보조)
API_DROUGHT = "15117185"    # 논가뭄지도 (지역 가뭄 패널)
API_RESERVOIR = "15099919"  # 저수지 수위정보 (선택)

HTTP_TIMEOUT_S = 5.0

DISCLAIMER = "공공데이터 기반 참고정보이며 최종 계약·분양은 공식 기관 확인이 필요합니다."

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
