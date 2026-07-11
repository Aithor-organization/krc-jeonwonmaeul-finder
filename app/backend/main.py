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
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

orch = Orchestrator()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "sample_mode": config.SAMPLE_MODE}


@app.post("/api/search", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
    return orch.search(query=req.query, structured=req.structured)


@app.get("/api/village/{gu_id}")
def village(gu_id: str) -> dict:
    for s in orch.client.get_sales():
        if s.get("gu_id") == gu_id:
            return {"sale": s, "village": orch.client.get_village(s.get("법정동코드"))}
    return {"error": "not_found", "gu_id": gu_id}


# 정적 프론트 서빙 (API 라우트 뒤에 mount → /api/* 우선)
if config.FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="frontend")
