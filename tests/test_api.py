from __future__ import annotations

from fastapi.testclient import TestClient

from sales_assistant.api.dependencies import (
    get_agent_service,
    get_metrics_service,
    get_repository,
    get_sync_service,
)
from sales_assistant.llm.agent import AgentQueryResponse
from sales_assistant.main import app
from sales_assistant.orchestration.salesforce_sync import SalesforceSyncSummary


class StubRepository:
    def healthcheck(self) -> bool:
        return True


class StubMetricsService:
    def get_pipeline_summary(self) -> dict[str, object]:
        return {
            "tool_used": "get_pipeline_summary",
            "data_updated_at": "2026-06-16T13:00:00",
            "warnings": [],
            "summary": {"open_opportunity_count": 3},
        }


class StubSyncService:
    def sync_open_pipeline(self, checkpoint: str | None = None) -> SalesforceSyncSummary:
        return SalesforceSyncSummary(
            alias_used="tivit-prod-api",
            opportunities=3,
            opportunity_items=4,
            data_updated_at="2026-06-16T13:00:00",
            latest_opportunity_system_modstamp="2026-06-16T13:00:00",
            latest_item_system_modstamp="2026-06-16T13:00:00",
            validation_summary={"unique_opportunities": 3},
        )


class StubAgentService:
    def query(self, question: str) -> AgentQueryResponse:
        return AgentQueryResponse(
            answer="Hay 3 oportunidades abiertas.",
            tool_used="get_pipeline_summary",
            data_updated_at="2026-06-16T13:00:00",
            warnings=[],
        )


def test_frontend_root_serves_minimal_ui() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "PoC Asistente Comercial TIVIT" in response.text
    assert "Actualizar datos" in response.text


def test_health_endpoint() -> None:
    app.dependency_overrides[get_repository] = StubRepository
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["curated_files_ready"] is True

    app.dependency_overrides.clear()


def test_pipeline_summary_endpoint() -> None:
    app.dependency_overrides[get_metrics_service] = StubMetricsService
    client = TestClient(app)

    response = client.get("/commercial/pipeline/summary")

    assert response.status_code == 200
    assert response.json()["summary"]["open_opportunity_count"] == 3

    app.dependency_overrides.clear()


def test_salesforce_sync_endpoint() -> None:
    app.dependency_overrides[get_sync_service] = StubSyncService
    client = TestClient(app)

    response = client.post("/salesforce/sync")

    assert response.status_code == 200
    assert response.json()["opportunities"] == 3

    app.dependency_overrides.clear()


def test_agent_query_endpoint_uses_stubbed_llm_service() -> None:
    app.dependency_overrides[get_agent_service] = StubAgentService
    client = TestClient(app)

    response = client.post(
        "/agent/query", json={"question": "¿Cuántas oportunidades abiertas hay?"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Hay 3 oportunidades abiertas.",
        "tool_used": "get_pipeline_summary",
        "data_updated_at": "2026-06-16T13:00:00",
        "warnings": [],
    }

    app.dependency_overrides.clear()
