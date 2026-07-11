"""파이프라인 조립 (기술명세 §2.1): guard → parse → fetch → score → evidence → panel → 고지."""
from __future__ import annotations

import config
import evidence as evidence_mod
import guards
import intent
import llm_intent
import scoring
from clients import KrcDataClient
from models import DroughtPanel, Evidence, SearchResponse, VillageCard


def _num(v):
    """안전 숫자 변환 — 실패 시 None (불량 원천 데이터로 인한 500 방지)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v):
    n = _num(v)
    return int(n) if n is not None else None


class Orchestrator:
    def __init__(self, client: KrcDataClient | None = None) -> None:
        self.client = client or KrcDataClient()

    def _empty(self, parsed, warnings) -> SearchResponse:
        return SearchResponse(
            query_parsed=parsed, top=[], drought_panel=None, evidence=[],
            disclaimer=config.DISCLAIMER, warnings=warnings,
        )

    def search(self, query: str | None = None, structured=None, top_n: int = 3) -> SearchResponse:
        warnings = list(self.client.warnings)

        # 1) Input Guard + 파싱 (structured 경로도 guard 적용 — 우회 방지)
        if structured is not None:
            _, blocked, _reasons = guards.inspect_input(getattr(structured, "raw", "") or "")
            if blocked:
                return self._empty(intent.parse(""), ["prompt injection 의심 패턴 감지 — 요청 차단"])
            parsed = structured
        else:
            cleaned, blocked, reasons = guards.inspect_input(query)
            if blocked:
                return self._empty(intent.parse(""), reasons)
            warnings.extend(reasons)
            if config.LLM_ENABLED:
                parsed, meta = llm_intent.parse(cleaned)
                if meta.get("model"):
                    warnings.append(f"자연어 파싱 모델: {meta['model']} ({meta['tier']} tier)")
                if meta.get("fallback"):
                    warnings.append(f"LLM 파싱 폴백(규칙 파서 사용): {meta.get('error', '')}")
            else:
                parsed = intent.parse(cleaned)

        # 조건 미인식 → 전체 덤프 대신 안내 (두 입력 경로 공통)
        if not (parsed.region.sido or parsed.sale_stage or parsed.budget_max_krw
                or parsed.preferences or parsed.household_min):
            if (query or getattr(parsed, "raw", "") or "").strip():
                warnings.append("조건을 인식하지 못했습니다. 지역·예산·분양 조건(예: '충남 예산 2억 분양 중')을 입력해 주세요.")
            return self._empty(parsed, warnings)

        if parsed.confidence < 0.6:
            warnings.append("입력 해석 신뢰도가 낮습니다. 지역·예산·분양 조건을 함께 입력하면 정확해집니다.")

        # 2) 전원마을 분양정보 조회. 진행단계 조건은 자동 완화하지 않음(위반 결과 노출 방지)
        sido = parsed.region.sido
        stages = parsed.sale_stage or None
        sales = self.client.get_sales(sido=sido, sigungu=parsed.region.sigungu, stages=stages)
        if not sales and stages:
            warnings.append("요청한 진행단계에 맞는 지구가 없습니다. 진행단계 조건을 바꿔 다시 검색해 보세요.")

        # 세대수 조건 필터 (계획세대수 기준). 미충족 시 완화 없이 빈 결과
        if parsed.household_min:
            filtered = [s for s in sales if (_num(s.get("계획세대수")) or 0) >= parsed.household_min]
            if filtered:
                sales = filtered
            elif sales:
                sales = []
                warnings.append(f"{parsed.household_min}세대 이상 조건에 맞는 지구가 없습니다.")

        # 예산은 참고용 — 분양가 데이터 부재로 필터 미적용 (정직 고지)
        if parsed.budget_max_krw:
            warnings.append("예산은 참고용입니다 — 공공 분양정보에 분양가가 없어 예산 필터는 적용되지 않습니다. 분양가는 공식 분양처에서 확인하세요.")

        if not sales:
            warnings.append("조건에 맞는 전원마을 분양 정보를 찾지 못했습니다.")

        # 3) 점수 + 카드 (물 정보 미포함, 수치 안전 변환, 출력 가드)
        cards: list[VillageCard] = []
        for sale in sales:
            village = self.client.get_village(sale.get("법정동코드"))
            score, grade, reasons = scoring.score_card(parsed, sale, village)
            cards.append(VillageCard(
                gu_id=str(sale.get("gu_id", "")),
                gu_name=guards.inspect_output(str(sale.get("지구명", ""))),
                sido=str(sale.get("시도명", "")),
                sigungu=str(sale.get("시군구", "")),
                eupmyeon=sale.get("읍면동"),
                sale_stage=sale.get("진행단계"),
                sale_rate=_num(sale.get("분양율")),
                planned_households=_int(sale.get("계획세대수")),
                population=_int(village.get("인구")) if village else None,
                vacant_houses=_int(village.get("빈집수")) if village else None,
                score=score, confidence_grade=grade,
                reasons=[guards.inspect_output(r) for r in reasons],
            ))
        cards.sort(key=lambda c: (c.score, 100 - (c.sale_rate if c.sale_rate is not None else 100)), reverse=True)
        top = cards[:top_n]

        # 4) Evidence 바인딩 — 미바인딩 시 경고 (수치는 카드 필드에서 구성되어 항상 바인딩)
        all_ev: list[Evidence] = []
        for c in top:
            ev = evidence_mod.build_evidence(c)
            if not evidence_mod.is_fully_bound(c, ev):
                warnings.append(f"{c.gu_name}: 일부 수치 근거 미바인딩 — 확인 불가 처리")
            all_ev.extend(ev)

        # 5) 지역 가뭄 패널 (점수와 분리) + 가뭄 수치 evidence 바인딩 (AC3)
        panel = None
        if top:
            d = self.client.get_drought(top[0].sigungu)
            if d:
                nr = _num(d.get("평년대비"))
                panel = DroughtPanel(
                    sigungu=str(d.get("시군구", "")),
                    drought_stage=d.get("가뭄단계") or config.drought_stage_from_ratio(nr),
                    normal_ratio=nr,
                    base_date=d.get("기준일자"),
                )
                if nr is not None:
                    all_ev.append(Evidence(
                        claim=f"[{panel.sigungu}] 평년대비 저수율 {nr}%",
                        api=config.API_DROUGHT, field="평년대비", value=nr))

        return SearchResponse(
            query_parsed=parsed, top=top, drought_panel=panel,
            evidence=all_ev, disclaimer=config.DISCLAIMER, warnings=warnings,
        )
