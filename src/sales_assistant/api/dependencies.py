from __future__ import annotations

from functools import lru_cache

from sales_assistant.business.commercial_tools import CommercialMetricsService
from sales_assistant.config import get_settings
from sales_assistant.ingestion.salesforce_cli_reader import SalesforceCliReader
from sales_assistant.llm.agent import (
    CommercialAgentService,
    ToolExecutionRecorder,
    build_langchain_agent,
)
from sales_assistant.llm.client import VertexModelFactory
from sales_assistant.llm.response_writer import ResponseWriter
from sales_assistant.orchestration.salesforce_sync import SalesforceSyncService
from sales_assistant.persistence.repository import CsvCuratedSalesRepository


@lru_cache(maxsize=1)
def get_repository() -> CsvCuratedSalesRepository:
    settings = get_settings()
    return CsvCuratedSalesRepository(settings.salesforce_curated_dir)


@lru_cache(maxsize=1)
def get_salesforce_reader() -> SalesforceCliReader:
    settings = get_settings()
    return SalesforceCliReader(
        org_alias=settings.salesforce_org_alias,
        timeout_seconds=settings.salesforce_cli_timeout_seconds,
        query_limit=settings.salesforce_query_limit,
        max_records=settings.salesforce_max_records,
    )


@lru_cache(maxsize=1)
def get_sync_service() -> SalesforceSyncService:
    settings = get_settings()
    return SalesforceSyncService(
        reader=get_salesforce_reader(),
        raw_dir=settings.salesforce_raw_dir,
        curated_dir=settings.salesforce_curated_dir,
    )


@lru_cache(maxsize=1)
def get_metrics_service() -> CommercialMetricsService:
    settings = get_settings()
    return CommercialMetricsService(
        repository=get_repository(),
        live_reader=get_salesforce_reader(),
        live_fallback_enabled=settings.salesforce_live_fallback_enabled,
    )


@lru_cache(maxsize=1)
def get_agent_service() -> CommercialAgentService:
    settings = get_settings()
    recorder = ToolExecutionRecorder()
    executor = build_langchain_agent(
        metrics_service=get_metrics_service(),
        model_factory=VertexModelFactory(settings),
        recorder=recorder,
    )
    return CommercialAgentService(
        executor=executor,
        response_writer=ResponseWriter(),
        recorder=recorder,
    )


def clear_service_caches() -> None:
    get_repository.cache_clear()
    get_salesforce_reader.cache_clear()
    get_sync_service.cache_clear()
    get_metrics_service.cache_clear()
    get_agent_service.cache_clear()
