"""FastAPI 앱 — 엔드포인트 3종 + 정적 프론트 서빙."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from models import SearchRequest, SearchResponse
from orchestrator import Orchestrator

app = FastAPI(title="전원마을 파인더", version="1.0.0",
              description="KRC 공공데이터 기반 '분양 가능한 전원마을' 실시간 검색")
# 공개 read-only API. 운영 배포 시 allow_origins를 실제 프론트 도메인으로 제한 권장.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

orch = Orchestrator()


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "sample_mode": config.SAMPLE_MODE,
        "llm_enabled": config.LLM_ENABLED,
        "llm_models": {
            "simple": config.LLM_MODEL_SIMPLE,
            "medium": config.LLM_MODEL_MEDIUM,
            "complex": config.LLM_MODEL_COMPLEX,
        } if config.LLM_ENABLED else None,
        # 서버에 키가 없어도 사용자가 화면에서 직접 키를 넣어 LLM 파싱을 쓸 수 있다
        "byok_supported": True,
    }


@app.get("/api/regions")
def regions() -> dict:
    """지역 드롭다운 목록.

    새 공공데이터 API를 부르지 않는다 — 검색에 쓰는 분양정보(전국 167건)에
    이미 시도·시군구가 들어 있어 그 데이터에서 집계한다. 따라서 이 목록은
    항상 "실제로 검색되는 지역"과 일치한다.
    """
    return orch.client.region_tree()


@app.post("/api/search", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
    # openai_api_key는 이 호출의 파싱에만 쓰이고 저장·로깅되지 않는다 (BYOK)
    return orch.search(query=req.query, structured=req.structured,
                       api_key=req.openai_api_key, filters=req.filters)


@app.get("/api/village/{gu_id}")
def village(gu_id: str) -> dict:
    for s in orch.client.get_sales():
        if s.get("gu_id") == gu_id:
            v = orch.client.get_village(s.get("법정동코드"))
            # 원본 dict 전체 노출 금지 — 허용 필드만 반환 (AC3/PII)
            return {
                "gu_id": s.get("gu_id"),
                "gu_name": s.get("지구명"),
                "sido": s.get("시도명"),
                "sigungu": s.get("시군구"),
                "eupmyeon": s.get("읍면동"),
                "sale_stage": s.get("진행단계"),
                "sale_rate": s.get("분양율"),
                "planned_households": s.get("계획세대수"),
                "population": v.get("인구") if v else None,
                "vacant_houses": v.get("빈집수") if v else None,
                "disclaimer": config.DISCLAIMER,
            }
    return {"error": "not_found", "gu_id": gu_id}


# 정적 프론트 서빙 (API 라우트 뒤에 mount → /api/* 우선)
if config.FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="frontend")
