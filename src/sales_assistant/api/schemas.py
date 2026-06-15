from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_configured: bool
    persistence_mode: str
    loaded_files: int
