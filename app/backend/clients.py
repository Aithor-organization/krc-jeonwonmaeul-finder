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
import time

import config
import krc_live
from krc_mapping import RATE_NOTE, STAGE_NOTE, VILLAGE_NOTE, map_sales


def _load(name: str) -> list[dict]:
    with open(config.SAMPLES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


SAMPLE_NOTE = "sample-mode: 공공데이터 서비스키가 없어 샘플 데이터로 동작합니다."


class KrcDataClient:
    def __init__(self, sample_mode: bool | None = None) -> None:
        forced_sample = config.SAMPLE_MODE if sample_mode is None else sample_mode
        self._live_possible = not forced_sample

        self.sample_mode = True         # 실제 로드 전까지는 샘플로 간주 (낙관 금지)
        self.live_active = False
        self.warnings: list[str] = []   # 조치가 필요한 문제
        self.notes: list[str] = []      # 데이터 성격 안내 (문제 아님)

        self._village = {v["법정동코드"]: v for v in _load("rural_village.json")}
        self._drought = {d["시군구"]: d for d in _load("drought.json")}
        self._sale: list[dict] | None = None
        self._retry_at = 0.0

    # --- 데이터 확보 (지연 로드 + 실패 재시도) ---
    def ensure_loaded(self) -> None:
        """분양 데이터를 확보한다. live 실패 시 샘플로 내려앉되 주기적으로 재시도.

        모듈 임포트가 아니라 첫 사용 시점에 부르는 이유: 서버리스 콜드스타트에
        상류 지연(최대 15초)이 그대로 얹히면 화면 HTML조차 그만큼 늦게 뜬다.
        이 앱은 프론트도 같은 함수가 서빙하므로 검색과 무관한 요청까지 느려진다.

        재시도가 필요한 이유: 한 번 실패한 채로 굳으면 그 인스턴스는 수명 내내
        샘플만 내놓는다. KRC 상류는 같은 요청도 성패가 갈리므로 회복 경로가 있어야 한다.
        """
        if not self._live_possible:                 # 키 없음 — 재시도해도 소용없다
            if self._sale is None:
                self._fall_back(SAMPLE_NOTE, is_note=True)
            return
        if self.live_active:                        # 이미 확보됨
            return
        if self._sale is not None and time.monotonic() < self._retry_at:
            return                                  # 직전 실패 — 쿨다운 중엔 샘플 유지

        try:
            self._sale = map_sales(krc_live.fetch_sales(config.KRC_SERVICE_KEY or ""))
            self.sample_mode = False
            self.live_active = True
            self.warnings = []
            self.notes = [STAGE_NOTE, VILLAGE_NOTE, RATE_NOTE]
        except krc_live.KrcApiError as e:
            self._retry_at = time.monotonic() + config.KRC_RETRY_AFTER_S
            self._fall_back(
                f"KRC API 호출 실패로 샘플 데이터로 대체했습니다: {e}", is_note=False)

    def _fall_back(self, message: str, is_note: bool) -> None:
        """샘플로 내려앉는다. 상태 메시지는 누적이 아니라 교체 — 인스턴스가 재사용되므로."""
        self._sale = _load("jeonwon_sale.json")
        self.sample_mode = True
        self.live_active = False
        self.notes = [message] if is_note else []
        self.warnings = [] if is_note else [message]

    # --- 전원마을 분양정보 (핵심) ---
    def get_sales(
        self,
        sido: str | None = None,
        sigungu: str | None = None,
        stages: list[str] | None = None,
    ) -> list[dict]:
        self.ensure_loaded()
        rows = list(self._sale or [])
        if sido:
            rows = [r for r in rows if r.get("시도명") == sido]
        if sigungu:
            rows = [r for r in rows if r.get("시군구") == sigungu]
        if stages:
            rows = [r for r in rows if r.get("진행단계") in stages]
        return rows

    def available_sigungu(self) -> list[str]:
        """현재 데이터에 실제로 존재하는 시군구 목록 (질의 매칭용)."""
        self.ensure_loaded()
        return sorted({str(r.get("시군구")) for r in (self._sale or []) if r.get("시군구")})

    # --- 농촌마을현황 (보조) ---
    def get_village(self, bjd_code: str | None) -> dict | None:
        # live-mode에서는 조인하지 않는다 (VILLAGE_NOTE로 고지됨)
        self.ensure_loaded()
        if self.live_active or not bjd_code:
            return None
        return self._village.get(bjd_code)

    # --- 논가뭄지도 (지역 가뭄 패널) ---
    def get_drought(self, sigungu: str | None) -> dict | None:
        if not sigungu:
            return None
        return self._drought.get(sigungu)
