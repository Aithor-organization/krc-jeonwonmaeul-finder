"""Pydantic 스키마 — 요청/응답/도메인 계약 (SPEC S5 고정)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Region(BaseModel):
    sido: str | None = None
    sigungu: str | None = None


class ParsedQuery(BaseModel):
    region: Region = Field(default_factory=Region)
    budget_max_krw: int | None = None
    sale_stage: list[str] = Field(default_factory=list)
    household_min: int | None = None
    preferences: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    raw: str = ""


class Evidence(BaseModel):
    claim: str
    api: str
    field: str
    value: object | None = None


class VillageCard(BaseModel):
    gu_id: str
    gu_name: str
    sido: str
    sigungu: str
    eupmyeon: str | None = None
    sale_stage: str | None = None
    # 원천 라벨 그대로. '분양중'은 원천에서 '주택건축 단계'라 **공사 중**이라는
    # 뜻인데, 우리 라벨만 보면 "지금 들어갈 수 있다"로 읽힌다.
    sale_stage_source: str | None = None
    sale_rate: float | None = None
    # 원천에 100을 넘는 값이 적혀 있어 표시를 보류한 경우 그 원본 값.
    # '없음'과 '범위를 벗어남'은 화면에서 같은 "확인 불가"로 보이지만
    # 이유가 다르다 — 이유까지 같게 말하면 그건 사실이 아니다.
    sale_rate_out_of_range: float | None = None
    # 확정 / 추정 / 보류 / 미상. 전에는 '수치 있음/없음' 둘뿐이라
    # **우리가 아는 17건이 정말 모르는 124건과 같은 칸**에 들어갔다.
    sale_rate_status: str = "미상"
    # 단계와 수치가 어긋나는 조합 (분양예정인데 100% 등). 값은 그대로 두고
    # 어긋난다는 사실만 알린다.
    sale_rate_anomaly: str | None = None
    planned_households: int | None = None
    population: int | None = None
    vacant_houses: int | None = None
    # 연령 16칸을 더해 인구 하나로 뭉개던 것을 되살린 값. 같은 "인구 61명"이라도
    # 그중 55명이 65세 이상이면 완전히 다른 마을이다.
    elderly_count: int | None = None
    elderly_ratio: int | None = None
    slate_houses: int | None = None      # 값이 있을 때만 (0=미조사 구분 불가)
    village_note: str | None = None      # 원천 마을 소개글 (선호 점수에는 미반영)
    village_note_truncated: bool = False
    # 마을 자원정보(resourceVill). 127곳 중 17곳만 등록돼 있어 **점수에는 넣지
    # 않는다** — 13%만 판정 가능한 조건을 점수화하면, 자원이 등록되지 않은
    # 나머지 110곳이 "자원이 없는 마을"로 깎인다. 미등록과 부재는 다르다.
    village_resources: dict[str, list[str]] | None = None
    # 통계표를 그대로 부은 항목(토양·암석 수치 등)은 따로 담아 접어 둔다.
    # 지우지 않는 이유 — 원문을 감추면 "근거 있는 사실 확인"이 아니게 된다.
    village_resources_detail: dict[str, list[str]] | None = None
    # 인구·빈집이 어느 마을 값인지. 분양 지구(예: 산북지구전원마을)와 이 마을
    # (예: 산북2리)은 서로 다른 대상이라, 이름 없이 숫자만 붙이면 지구의 값으로
    # 읽힌다 — 실제로 "빈집 0인데 왜 추천하냐"는 오독이 나왔다.
    village_name: str | None = None
    score: float = 0.0
    confidence_grade: str = "D"
    reasons: list[str] = Field(default_factory=list)


class DroughtPanel(BaseModel):
    sigungu: str
    drought_stage: str
    normal_ratio: float | None = None
    base_date: str | None = None
    note: str = "논가뭄지도 연1회 갱신·참고용"


class FunnelStep(BaseModel):
    """후보가 줄어든 단계 하나. 탈락 건수를 함께 담아 '숨긴 게 아님'을 보인다."""
    label: str
    count: int
    dropped: int = 0
    note: str | None = None


class ScoreTerm(BaseModel):
    """점수 한 항의 전개. scoring._terms가 만든 값을 그대로 옮긴다."""
    label: str
    weight: float
    value: float
    contribution: float
    basis: str


class CardScore(BaseModel):
    gu_id: str
    gu_name: str
    terms: list[ScoreTerm] = Field(default_factory=list)
    total: float


class SearchTrace(BaseModel):
    """이 검색 한 건이 어떻게 계산됐는지. 서버에 저장하지 않고 응답에만 실린다.

    할루시네이션 여부를 판단하려면 '모델이 무엇을 했나'가 아니라
    '모델이 어디까지만 했나'를 봐야 한다 — parser/llm_scope가 그 경계를 명시한다.
    """
    parser: str                 # 문장을 조건으로 바꾼 주체
    llm_scope: str              # LLM이 관여한 범위 (순위·수치 제외)
    formula: str                # 점수 산식
    deterministic: bool = True  # 같은 입력 → 같은 결과
    funnel: list[FunnelStep] = Field(default_factory=list)
    scores: list[CardScore] = Field(default_factory=list)


class SearchFilters(BaseModel):
    """사용자가 화면 목록에서 직접 고른 조건.

    문장과 함께 올 수 있다. 이때 문장은 그대로 해석하되 여기 담긴 항목만
    해석 결과를 덮어쓴다 — 목록에서 고른 값은 이미 확정된 조건이라 추측으로
    바꿀 이유가 없다. 예: 드롭다운 '구례군' + 문장 '조용하고 2억 이하'
    → 지역은 구례군 확정, 예산·선호는 문장에서.
    """
    sido: str | None = None
    sigungu: str | None = None
    sale_stage: str | None = None


class SearchRequest(BaseModel):
    query: str | None = None
    structured: ParsedQuery | None = None
    filters: SearchFilters | None = None
    # 🔴 이 필드가 없어서 요청에 top_n을 실어도 **조용히 무시**됐다.
    # orchestrator는 top_n을 받는데 요청 스키마에 없으니 Pydantic이 버렸고,
    # 무엇을 넣든 항상 3건만 돌아왔다. 전체 목록 페이지가 필요해지며 드러났다.
    # 상한 167 = 원천 지구 전체 (그 이상은 존재하지 않는다).
    top_n: int = Field(default=3, ge=1, le=167)
    # 사용자가 화면에서 직접 입력하는 OpenAI 키(BYOK). 서버는 저장·로깅하지 않고
    # 해당 요청의 파싱에만 쓰고 버린다. 응답에도 절대 포함하지 않는다.
    openai_api_key: str | None = None


class SearchResponse(BaseModel):
    query_parsed: ParsedQuery
    top: list[VillageCard]
    drought_panel: DroughtPanel | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    disclaimer: str
    # warnings = 사용자가 조치해야 할 문제 (조건 미인식·0건·차단·호출 실패)
    warnings: list[str] = Field(default_factory=list)
    # notes = 데이터 성격을 알리는 상시 안내 (단계 변환·미제공 항목). 문제가 아니므로 분리한다.
    notes: list[str] = Field(default_factory=list)
    # trace = 이 결과가 나온 계산 내역 (화면의 "계산 내역" 패널이 그린다)
    trace: SearchTrace | None = None
