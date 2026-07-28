"""KRC 공공데이터 클라이언트 (기술명세 §3).

- sample-mode: data/samples/*.json 로드·필터 (키 없이 오프라인 동작)
- live-mode: KRC_SERVICE_KEY 설정 시 apis.data.go.kr 실호출 후 내부 스키마로 매핑.
  전원마을 분양정보는 전국 167건이라 1회 전량 수신 후 기존 필터 로직을 그대로 재사용한다.
  호출 실패 시 샘플로 fallback하고 경고를 남긴다(조용한 실패 금지, §3.4).

농촌마을현황(인구·빈집수)은 전국 2.8만 건 규모라 live 조인을 하지 않는다 —
live-mode에서 get_village는 None을 반환하고 그 사실을 경고로 고지한다.
"""
from __future__ import annotations

import json

import config
import krc_live
from krc_mapping import STAGE_NOTE, VILLAGE_NOTE, map_sales


def _load(name: str) -> list[dict]:
    with open(config.SAMPLES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


class KrcDataClient:
    def __init__(self, sample_mode: bool | None = None) -> None:
        self.sample_mode = config.SAMPLE_MODE if sample_mode is None else sample_mode
        self.warnings: list[str] = []   # 조치가 필요한 문제
        self.notes: list[str] = []      # 데이터 성격 안내 (문제 아님)
        self.live_active = False

        self._village = {v["법정동코드"]: v for v in _load("rural_village.json")}
        self._drought = {d["시군구"]: d for d in _load("drought.json")}

        if self.sample_mode:
            self._sale = _load("jeonwon_sale.json")
            self.notes.append(
                "sample-mode: 공공데이터 서비스키가 없어 샘플 데이터로 동작합니다."
            )
            return

        # live-mode: 실호출 → 매핑. 실패하면 샘플로 내려앉되 반드시 고지한다.
        try:
            self._sale = map_sales(krc_live.fetch_sales(config.KRC_SERVICE_KEY or ""))
            self.live_active = True
            self.notes.append(STAGE_NOTE)
            self.notes.append(VILLAGE_NOTE)
        except krc_live.KrcApiError as e:
            self._sale = _load("jeonwon_sale.json")
            self.sample_mode = True
            self.warnings.append(f"KRC API 호출 실패로 샘플 데이터로 대체했습니다: {e}")

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

    def available_sigungu(self) -> list[str]:
        """현재 데이터에 실제로 존재하는 시군구 목록 (질의 매칭용)."""
        return sorted({str(r.get("시군구")) for r in self._sale if r.get("시군구")})

    # --- 농촌마을현황 (보조) ---
    def get_village(self, bjd_code: str | None) -> dict | None:
        # live-mode에서는 조인하지 않는다 (VILLAGE_NOTE로 고지됨)
        if self.live_active or not bjd_code:
            return None
        return self._village.get(bjd_code)

    # --- 논가뭄지도 (지역 가뭄 패널) ---
    def get_drought(self, sigungu: str | None) -> dict | None:
        if not sigungu:
            return None
        return self._drought.get(sigungu)
