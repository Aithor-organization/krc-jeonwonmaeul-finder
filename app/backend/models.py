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
    sale_rate: float | None = None
    planned_households: int | None = None
    population: int | None = None
    vacant_houses: int | None = None
    score: float = 0.0
    confidence_grade: str = "D"
    reasons: list[str] = Field(default_factory=list)


class DroughtPanel(BaseModel):
    sigungu: str
    drought_stage: str
    normal_ratio: float | None = None
    base_date: str | None = None
    note: str = "논가뭄지도 연1회 갱신·참고용"


class SearchRequest(BaseModel):
    query: str | None = None
    structured: ParsedQuery | None = None


class SearchResponse(BaseModel):
    query_parsed: ParsedQuery
    top: list[VillageCard]
    drought_panel: DroughtPanel | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    disclaimer: str
    warnings: list[str] = Field(default_factory=list)
