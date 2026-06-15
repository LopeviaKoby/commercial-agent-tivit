from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from sales_assistant import __version__
from sales_assistant.api.schemas import HealthResponse
from sales_assistant.config import get_settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def healthcheck() -> HealthResponse:
    settings = get_settings()
    input_dir = Path(settings.data_input_dir)
    loaded_files = 0

    if input_dir.exists():
        loaded_files = sum(1 for item in input_dir.iterdir() if item.is_file())

    return HealthResponse(
        status="ok",
        version=__version__,
        llm_configured=bool(settings.gemini_api_key),
        persistence_mode=settings.persistence_mode,
        loaded_files=loaded_files,
    )
