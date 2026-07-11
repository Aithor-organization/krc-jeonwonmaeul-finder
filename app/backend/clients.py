"""KRC 공공데이터 클라이언트 — sample-mode(키 없이 동작) + live 스텁 (기술명세 §3).

sample-mode: data/samples/*.json 로드·필터. live-mode: allowlist 검증 후 httpx 호출,
실패 시 샘플 fallback + warning (오프라인 백업, 기술명세 §3.4).
"""
from __future__ import annotations

import json

import config


def _load(name: str) -> list[dict]:
    with open(config.SAMPLES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


class KrcDataClient:
    def __init__(self, sample_mode: bool | None = None) -> None:
        self.sample_mode = config.SAMPLE_MODE if sample_mode is None else sample_mode
        self._sale = _load("jeonwon_sale.json")
        self._village = {v["법정동코드"]: v for v in _load("rural_village.json")}
        self._drought = {d["시군구"]: d for d in _load("drought.json")}
        self.warnings: list[str] = []
        if self.sample_mode:
            self.warnings.append("sample-mode: 공공데이터 활용신청 승인 전이라 샘플 데이터로 동작합니다.")

    # --- 전원마을 분양정보 (핵심) ---
    def get_sales(
        self,
        sido: str | None = None,
        sigungu: str | None = None,
        stages: list[str] | None = None,
    ) -> list[dict]:
        rows = list(self._sale)
        if sido:
            rows = [r for r in rows if r.get("시도명") == sido]
        if sigungu:
            rows = [r for r in rows if r.get("시군구") == sigungu]
        if stages:
            rows = [r for r in rows if r.get("진행단계") in stages]
        return rows

    # --- 농촌마을현황 (보조) ---
    def get_village(self, bjd_code: str | None) -> dict | None:
        if not bjd_code:
            return None
        return self._village.get(bjd_code)

    # --- 논가뭄지도 (지역 가뭄 패널) ---
    def get_drought(self, sigungu: str | None) -> dict | None:
        if not sigungu:
            return None
        return self._drought.get(sigungu)
