from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from sales_assistant import __version__
from sales_assistant.api.dependencies import (
    get_agent_service,
    get_metrics_service,
    get_repository,
    get_sync_service,
)
from sales_assistant.api.schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
    HealthResponse,
    PipelineSummaryResponse,
    SalesforceSyncResponse,
)
from sales_assistant.business.commercial_tools import CommercialMetricsService
from sales_assistant.config import get_settings
from sales_assistant.llm.agent import CommercialAgentService
from sales_assistant.llm.client import LLMConfigurationError, VertexModelFactory
from sales_assistant.orchestration.salesforce_sync import (
    SalesforceSyncService,
    sync_summary_to_dict,
)
from sales_assistant.persistence.repository import CsvCuratedSalesRepository

LOGGER = logging.getLogger(__name__)

router = APIRouter()
FRONTEND_PATH = Path(__file__).with_name("frontend.html")


@router.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(FRONTEND_PATH)


@router.get("/health", response_model=HealthResponse, tags=["health"])
def healthcheck(
    repository: CsvCuratedSalesRepository = Depends(get_repository),  # noqa: B008
) -> HealthResponse:
    settings = get_settings()
    llm_configured = VertexModelFactory(settings).is_configured()

    return HealthResponse(
        status="ok",
        version=__version__,
        llm_configured=llm_configured,
        persistence_mode=settings.persistence_mode,
        curated_files_ready=repository.healthcheck(),
    )


@router.post("/salesforce/sync", response_model=SalesforceSyncResponse, tags=["salesforce"])
def sync_salesforce(
    sync_service: SalesforceSyncService = Depends(get_sync_service),  # noqa: B008
) -> SalesforceSyncResponse:
    try:
        summary = sync_service.sync_open_pipeline()
    except Exception as error:
        LOGGER.exception("Salesforce sync failed")
        raise HTTPException(status_code=500, detail=str(error)) from error

    return SalesforceSyncResponse(**sync_summary_to_dict(summary))


@router.get(
    "/commercial/pipeline/summary",
    response_model=PipelineSummaryResponse,
    tags=["commercial"],
)
def get_pipeline_summary(
    metrics_service: CommercialMetricsService = Depends(get_metrics_service),  # noqa: B008
) -> PipelineSummaryResponse:
    return PipelineSummaryResponse(**metrics_service.get_pipeline_summary())


@router.post("/agent/query", response_model=AgentQueryResponse, tags=["agent"])
def query_agent(
    request: AgentQueryRequest,
    agent_service: CommercialAgentService = Depends(get_agent_service),  # noqa: B008
) -> AgentQueryResponse:
    try:
        response = agent_service.query(request.question)
    except (LLMConfigurationError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        LOGGER.exception("Agent query failed")
        raise HTTPException(status_code=500, detail=str(error)) from error

    return AgentQueryResponse(
        answer=response.answer,
        tool_used=response.tool_used,
        data_updated_at=response.data_updated_at,
        warnings=response.warnings,
    )
