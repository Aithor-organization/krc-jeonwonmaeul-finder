"""파이프라인 조립 (기술명세 §2.1): guard → parse → fetch → score → evidence → panel → 고지."""
from __future__ import annotations

import config
import evidence as evidence_mod
import guards
import intent
import llm_intent
import scoring
from clients import KrcDataClient
from models import (CardScore, DroughtPanel, Evidence, FunnelStep, ScoreTerm,
                    SearchResponse, SearchTrace, VillageCard)

# LLM이 관여하는 범위. 순위·점수·수치는 전부 결정론 코드가 만든다.
LLM_SCOPE = "문장 → 검색 조건 변환에만. 순위·점수·수치는 관여하지 않습니다."
RULE_PARSER = "규칙 파서 (결정론, 외부 호출 없음)"


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


# 지구는 뒤로 가지 않는다 — 중복 레코드 중 더 진행된 쪽이 최신 상태다
_STAGE_ORDER = {"분양예정": 0, "분양중": 1, "분양완료": 2}


def _dedupe_by_gu_id(paired: list[tuple]) -> tuple[list[tuple], int]:
    """같은 지구가 값이 다른 채 중복 등록된 것을 하나로 합친다.

    원천 API가 같은 inbpnCode로 서로 모순되는 레코드를 반환한다 (13쌍 실측:
    달두루=입주완료 vs 주택건축, 공정=50 vs 54세대). 그대로 두면 Top 3에 같은
    이름이 두 번 나오고 세대수·단계가 어긋나 보인다. 정렬 순서는 보존한다.
    """
    best: dict[str, tuple] = {}
    order: list[str] = []
    conflicts = 0
    for card, bd in paired:
        key = card.gu_id or f"_{id(card)}"
        if key not in best:
            best[key] = (card, bd)
            order.append(key)
            continue
        conflicts += 1
        if _STAGE_ORDER.get(card.sale_stage, -1) > _STAGE_ORDER.get(best[key][0].sale_stage, -1):
            best[key] = (card, bd)
    return [best[k] for k in order], conflicts


class Orchestrator:
    def __init__(self, client: KrcDataClient | None = None) -> None:
        self.client = client or KrcDataClient()

    def _empty(self, parsed, warnings) -> SearchResponse:
        return SearchResponse(
            query_parsed=parsed, top=[], drought_panel=None, evidence=[],
            disclaimer=config.DISCLAIMER, warnings=warnings,
            notes=list(self.client.notes),
        )

    def search(self, query: str | None = None, structured=None, top_n: int = 3,
               api_key: str | None = None, filters=None) -> SearchResponse:
        # 데이터 상태를 먼저 확정해야 아래 warnings/notes가 이번 요청의 실제 상태를 담는다
        # (클라이언트는 지연 로드 + 실패 재시도라 요청마다 상태가 바뀔 수 있다).
        self.client.ensure_loaded()
        warnings = list(self.client.warnings)
        notes = list(self.client.notes)

        # 1) Input Guard + 파싱 (structured 경로도 guard 적용 — 우회 방지)
        parser_label = RULE_PARSER
        llm_used = False
        if structured is not None:
            _, blocked, _reasons = guards.inspect_input(getattr(structured, "raw", "") or "")
            if blocked:
                return self._empty(intent.parse(""), ["prompt injection 의심 패턴 감지 — 요청 차단"])
            parsed = structured
            parser_label = "구조화 입력 (문장 파싱 없음)"
        else:
            cleaned, blocked, reasons = guards.inspect_input(query)
            if blocked:
                return self._empty(intent.parse(""), reasons)
            warnings.extend(reasons)
            # 사용자가 화면에서 키를 넣었으면 서버 설정과 무관하게 LLM 경로를 쓴다 (BYOK)
            user_key = (api_key or "").strip()
            if user_key or config.LLM_ENABLED:
                parsed, meta = llm_intent.parse(cleaned, api_key=user_key or None)
                if meta.get("model"):
                    notes.append(f"자연어 파싱 모델: {meta['model']} ({meta['tier']} tier)")
                if meta.get("fallback"):
                    # meta['error']는 llm_intent.redact()로 키가 마스킹된 상태
                    warnings.append(f"LLM 파싱 폴백(규칙 파서 사용): {meta.get('error', '')}")
                # 폴백이면 실제로 문장을 해석한 건 규칙 파서다 — 모델명을 적으면 거짓이 된다
                if meta.get("model") and not meta.get("fallback"):
                    parser_label = f"{meta['model']} ({meta['tier']} tier)"
                    llm_used = True
            else:
                parsed = intent.parse(cleaned)

            # 시군구는 데이터에 존재하는 이름으로만 확정한다 — LLM 답도 예외가 아니다.
            # LLM은 "충남 예산 2억"의 '예산'을 시군구와 금액 양쪽으로 동시에 읽는다
            # (실측: sigungu='예산' + budget=2억 → 예산군 1건으로 좁혀져 0건 반환).
            # match_sigungu가 그 충돌 가드를 이미 갖고 있으므로 통과시켜 검증한다.
            matched = intent.match_sigungu(cleaned, self.client.available_sigungu())
            if parsed.region.sigungu and matched != parsed.region.sigungu:
                if matched:
                    parsed.region.sigungu = matched          # 예: '예산' → '예산군' 정규화
                else:
                    # 데이터에 없거나 금액과 충돌 → 지역 조건으로 쓰지 않는다
                    dropped = parsed.region.sigungu
                    parsed.region.sigungu = None
                    notes.append(
                        f"'{dropped}'은(는) 지역 조건으로 쓰지 않았습니다 "
                        "— 데이터에 없는 이름이거나 금액 표현과 겹칩니다.")
            elif not parsed.region.sigungu:
                parsed.region.sigungu = matched

        # 1-bis) 화면에서 고른 조건은 문장 해석보다 우선한다.
        #
        # match_sigungu 검증 **뒤에** 적용하는 이유: 그 검증은 문장에서 뽑은
        # 이름이 데이터에 실재하는지 확인하는 절차인데, 여기 오는 값은 애초에
        # /api/regions 목록에서 고른 것이라 검증 대상이 아니다. 앞에 두면
        # 사용자가 고른 시군구를 문장 기준으로 지워버린다.
        applied: list[str] = []
        if filters is not None:
            if getattr(filters, "sido", None):
                parsed.region.sido = filters.sido
                applied.append(filters.sido)
            if getattr(filters, "sigungu", None):
                parsed.region.sigungu = filters.sigungu
                applied.append(filters.sigungu)
            if getattr(filters, "sale_stage", None):
                parsed.sale_stage = [filters.sale_stage]
                applied.append(filters.sale_stage)
            if applied and query:
                notes.append(
                    "직접 고른 조건(" + " · ".join(applied) + ")을 문장 해석보다 우선 적용했습니다"
                    " — 나머지 조건은 문장에서 읽었습니다.")

        # 조건 미인식 → 전체 덤프 대신 안내 (두 입력 경로 공통)
        if not (parsed.region.sido or parsed.region.sigungu or parsed.sale_stage
                or parsed.budget_max_krw or parsed.preferences or parsed.household_min):
            if (query or getattr(parsed, "raw", "") or "").strip():
                warnings.append("조건을 인식하지 못했습니다. 지역·예산·분양 조건(예: '충남 예산 2억 분양 중')을 입력해 주세요.")
            return self._empty(parsed, warnings)

        if parsed.confidence < 0.6:
            warnings.append("입력 해석 신뢰도가 낮습니다. 지역·예산·분양 조건을 함께 입력하면 정확해집니다.")

        # 2) 전원마을 분양정보 조회. 진행단계 조건은 자동 완화하지 않음(위반 결과 노출 방지)
        #    단계별로 나눠 조회하는 이유: 각 조건에서 몇 건이 떨어졌는지 화면에 보이기 위함.
        #    167건 규모의 메모리 필터라 4회 순회 비용은 무시할 수 있다.
        sido = parsed.region.sido
        sigungu = parsed.region.sigungu
        stages = parsed.sale_stage or None

        funnel: list[FunnelStep] = []
        prev = self.client.get_sales()
        funnel.append(FunnelStep(label="전국 전원마을 분양정보", count=len(prev)))

        if sido:
            cur = self.client.get_sales(sido=sido)
            funnel.append(FunnelStep(label=f"시도 = {sido}", count=len(cur),
                                     dropped=len(prev) - len(cur)))
            prev = cur
        if sigungu:
            cur = self.client.get_sales(sido=sido, sigungu=sigungu)
            funnel.append(FunnelStep(label=f"시군구 = {sigungu}", count=len(cur),
                                     dropped=len(prev) - len(cur)))
            prev = cur
        if stages:
            cur = self.client.get_sales(sido=sido, sigungu=sigungu, stages=stages)
            funnel.append(FunnelStep(label=f"진행단계 ∈ {', '.join(stages)}", count=len(cur),
                                     dropped=len(prev) - len(cur)))
            prev = cur

        sales = prev
        if not sales and stages:
            warnings.append("요청한 진행단계에 맞는 지구가 없습니다. 진행단계 조건을 바꿔 다시 검색해 보세요.")

        # 세대수 조건 필터 (계획세대수 기준). 미충족 시 완화 없이 빈 결과
        if parsed.household_min:
            filtered = [s for s in sales if (_num(s.get("계획세대수")) or 0) >= parsed.household_min]
            before = len(sales)
            if filtered:
                sales = filtered
            elif sales:
                sales = []
                warnings.append(f"{parsed.household_min}세대 이상 조건에 맞는 지구가 없습니다.")
            funnel.append(FunnelStep(label=f"계획세대수 ≥ {parsed.household_min}",
                                     count=len(sales), dropped=before - len(sales)))

        # 예산은 참고용 — 분양가 데이터 부재로 필터 미적용 (정직 고지)
        if parsed.budget_max_krw:
            warnings.append("예산은 참고용입니다 — 공공 분양정보에 분양가가 없어 예산 필터는 적용되지 않습니다. 분양가는 공식 분양처에서 확인하세요.")

        if not sales:
            warnings.append("조건에 맞는 전원마을 분양 정보를 찾지 못했습니다.")

        # 3) 점수 + 카드 (물 정보 미포함, 수치 안전 변환, 출력 가드)
        cards: list[VillageCard] = []
        # 🔴 gu_id로 키를 잡으면 안 된다 — 원천 API가 같은 inbpnCode로 값이 다른
        # 레코드를 13쌍 반환한다(실측). dict 키가 충돌하면 한 카드가 다른 지구의
        # 산식을 물고 와서 "0.5×1 + 0.3×1 + 0.2×0.5 = 0.45" 같은 틀린 식이 표시된다.
        # 카드와 1:1로 붙는 리스트를 쓴다 (인덱스 = 카드 순서).
        breakdowns: list[list[dict]] = []
        for sale in sales:
            village = self.client.get_village(sale.get("법정동코드"))
            score, grade, reasons = scoring.score_card(parsed, sale, village)
            breakdowns.append(scoring.score_breakdown(parsed, sale, village))
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
                village_name=guards.inspect_output(str(village.get("마을명") or "")) or None
                             if village else None,
                score=score, confidence_grade=grade,
                reasons=[guards.inspect_output(r) for r in reasons],
            ))
        # 카드와 산식을 한 쌍으로 묶어 정렬 — 따로 정렬하면 짝이 어긋난다
        paired = list(zip(cards, breakdowns))
        paired.sort(key=lambda cb: (cb[0].score,
                                    100 - (cb[0].sale_rate if cb[0].sale_rate is not None else 100)),
                    reverse=True)

        paired, conflicts = _dedupe_by_gu_id(paired)
        if conflicts:
            warnings.append(
                f"공공데이터에 같은 지구가 서로 다른 값으로 {conflicts}건 중복 등록되어 있어, "
                "가장 진행된 단계의 기록만 표시합니다.")

        cards = [c for c, _ in paired]
        top_pairs = paired[:top_n]
        top = [c for c, _ in top_pairs]
        if cards:
            funnel.append(FunnelStep(
                label=f"점수순 상위 {top_n}건 표시", count=len(top),
                dropped=len(cards) - len(top),
                note="탈락이 아니라 표시 개수 제한입니다 — 조건은 모두 통과했습니다."
                if len(cards) > len(top) else None))

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

        # 6) 계산 내역 — 이 응답에만 실리고 서버에는 남기지 않는다
        #    ("검색 문장 저장 0건" 주장과 충돌하지 않도록 저장 경로를 만들지 않음)
        trace = SearchTrace(
            parser=parser_label,
            llm_scope=LLM_SCOPE,
            # 🔴 LLM이 문장을 해석하면 같은 질의도 다른 조건으로 읽힐 수 있다
            # (실측: "전남에서 조용하고 아직 안 팔린 마을" 5회 중 1회가 분양완료로 해석).
            # 순위 계산은 언제나 결정론이지만, 그 앞단이 흔들리면 최종 결과는
            # 재현되지 않는다 — 여기서 참이라고 말하면 화면이 거짓말을 한다.
            deterministic=llm_used is False,
            formula=scoring.FORMULA,
            funnel=funnel,
            scores=[
                CardScore(
                    gu_id=c.gu_id, gu_name=c.gu_name, total=c.score,
                    terms=[ScoreTerm(**t) for t in bd],
                )
                for c, bd in top_pairs
            ],
        )

        return SearchResponse(
            query_parsed=parsed, top=top, drought_panel=panel,
            evidence=all_ev, disclaimer=config.DISCLAIMER, warnings=warnings,
            notes=notes, trace=trace,
        )
