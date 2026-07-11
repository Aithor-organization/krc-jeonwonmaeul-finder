"""파이프라인 조립 (기술명세 §2.1): guard → parse → fetch → score → evidence → panel → 고지."""
from __future__ import annotations

import config
import evidence as evidence_mod
import guards
import intent
import scoring
from clients import KrcDataClient
from models import DroughtPanel, SearchResponse, VillageCard


class Orchestrator:
    def __init__(self, client: KrcDataClient | None = None) -> None:
        self.client = client or KrcDataClient()

    def search(self, query: str | None = None, structured=None, top_n: int = 3) -> SearchResponse:
        warnings = list(self.client.warnings)

        # 1) Input Guard + 파싱
        if structured is not None:
            parsed = structured
        else:
            cleaned, blocked, reasons = guards.inspect_input(query)
            if blocked:
                return SearchResponse(
                    query_parsed=intent.parse(""),
                    top=[], drought_panel=None, evidence=[],
                    disclaimer=config.DISCLAIMER, warnings=reasons,
                )
            warnings.extend(reasons)
            parsed = intent.parse(cleaned)

        # 조건을 하나도 인식하지 못하면 전체 덤프 대신 안내 (검색 서비스 정직성)
        if structured is None and not (
            parsed.region.sido or parsed.sale_stage or parsed.budget_max_krw
            or parsed.preferences or parsed.household_min
        ):
            if (query or "").strip():
                warnings.append("조건을 인식하지 못했습니다. 지역·예산·분양 조건(예: '충남 예산 2억 분양 중')을 입력해 주세요.")
            return SearchResponse(
                query_parsed=parsed, top=[], drought_panel=None, evidence=[],
                disclaimer=config.DISCLAIMER, warnings=warnings,
            )

        if parsed.confidence < 0.6:
            warnings.append("입력 해석 신뢰도가 낮습니다. 지역·예산·분양 조건을 함께 입력하면 정확해집니다.")

        # 2) 전원마을 분양정보 조회 (지역 + 진행단계)
        sido = parsed.region.sido
        stages = parsed.sale_stage or None
        sales = self.client.get_sales(sido=sido, sigungu=parsed.region.sigungu, stages=stages)
        if not sales and stages:
            sales = self.client.get_sales(sido=sido, sigungu=parsed.region.sigungu)
            if sales:
                warnings.append("요청한 진행단계 결과가 없어 전체 진행단계를 포함했습니다.")
        if not sales:
            warnings.append("조건에 맞는 전원마을 분양 정보를 찾지 못했습니다.")

        # 3) 점수 + 카드 (물 정보 미포함)
        cards: list[VillageCard] = []
        for sale in sales:
            village = self.client.get_village(sale.get("법정동코드"))
            score, grade, reasons = scoring.score_card(parsed, sale, village)
            cards.append(VillageCard(
                gu_id=sale.get("gu_id", ""),
                gu_name=sale.get("지구명", ""),
                sido=sale.get("시도명", ""),
                sigungu=sale.get("시군구", ""),
                eupmyeon=sale.get("읍면동"),
                sale_stage=sale.get("진행단계"),
                sale_rate=sale.get("분양율"),
                planned_households=sale.get("계획세대수"),
                population=village.get("인구") if village else None,
                vacant_houses=village.get("빈집수") if village else None,
                score=score, confidence_grade=grade, reasons=reasons,
            ))
        cards.sort(key=lambda c: (c.score, 100 - (c.sale_rate if c.sale_rate is not None else 100)), reverse=True)
        top = cards[:top_n]

        # 4) Evidence 바인딩 (미바인딩 차단)
        all_ev = []
        for c in top:
            ev = evidence_mod.build_evidence(c)
            if not evidence_mod.is_fully_bound(c, ev):
                warnings.append(f"{c.gu_name}: 일부 수치 근거 미바인딩 — 확인 불가 처리")
            all_ev.extend(ev)

        # 5) 지역 가뭄 패널 (점수와 분리, 시군 단위)
        panel = None
        if top:
            d = self.client.get_drought(top[0].sigungu)
            if d:
                panel = DroughtPanel(
                    sigungu=d.get("시군구", ""),
                    drought_stage=d.get("가뭄단계") or config.drought_stage_from_ratio(d.get("평년대비")),
                    normal_ratio=d.get("평년대비"),
                    base_date=d.get("기준일자"),
                )

        return SearchResponse(
            query_parsed=parsed, top=top, drought_panel=panel,
            evidence=all_ev, disclaimer=config.DISCLAIMER, warnings=warnings,
        )
