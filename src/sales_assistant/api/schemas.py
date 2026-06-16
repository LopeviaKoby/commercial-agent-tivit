from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_configured: bool
    persistence_mode: str
    curated_files_ready: bool


class SalesforceSyncResponse(BaseModel):
    alias_used: str
    opportunities: int
    opportunity_items: int
    data_updated_at: str | None
    latest_opportunity_system_modstamp: str | None
    latest_item_system_modstamp: str | None
    validation_summary: dict[str, Any]


class AgentQueryRequest(BaseModel):
    question: str = Field(..., min_length=3)


class AgentQueryResponse(BaseModel):
    answer: str
    tool_used: str | None
    data_updated_at: str | None
    warnings: list[str]


class PipelineSummaryResponse(BaseModel):
    tool_used: str
    data_updated_at: str | None
    warnings: list[str]
    summary: dict[str, Any]
