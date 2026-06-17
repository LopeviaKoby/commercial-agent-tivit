from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, Field

from sales_assistant.business.commercial_tools import CommercialMetricsService
from sales_assistant.llm.client import VertexModelFactory
from sales_assistant.llm.response_writer import ResponseWriter

SYSTEM_PROMPT = (
    "Eres un asistente comercial de TIVIT. "
    "Siempre usa exactamente una herramienta determinista para responder preguntas de negocio. "
    "No inventes métricas. No sumes monedas distintas. "
    "Responde en español, de forma breve, y menciona cuándo se actualizaron los datos. "
    "Si la herramienta devuelve warnings, incorpóralos en la respuesta."
)


class TVTInput(BaseModel):
    tvt: str = Field(..., description="Código TVT exacto de la oportunidad.")


class AgentExecutor(Protocol):
    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(slots=True)
class ToolExecutionRecorder:
    last_tool_name: str | None = None
    last_payload: dict[str, Any] | None = None

    def record(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.last_tool_name = tool_name
        self.last_payload = payload
        return payload

    def reset(self) -> None:
        self.last_tool_name = None
        self.last_payload = None


@dataclass(frozen=True, slots=True)
class AgentQueryResponse:
    answer: str
    tool_used: str | None
    data_updated_at: str | None
    warnings: list[str] = field(default_factory=list)


def build_langchain_agent(
    metrics_service: CommercialMetricsService,
    model_factory: VertexModelFactory,
    recorder: ToolExecutionRecorder,
) -> AgentExecutor:
    try:
        from langchain.agents import create_agent
        from langchain.tools import tool
    except ImportError as error:
        raise RuntimeError(
            "LangChain no está disponible. Instala langchain y langgraph para habilitar el agente."
        ) from error

    @tool
    def get_pipeline_summary() -> dict[str, Any]:
        """Obtiene el resumen del pipeline abierto actual."""
        return recorder.record("get_pipeline_summary", metrics_service.get_pipeline_summary())

    @tool
    def get_pipeline_by_country() -> dict[str, Any]:
        """Cuenta oportunidades abiertas por país y separa ACV por moneda."""
        return recorder.record("get_pipeline_by_country", metrics_service.get_pipeline_by_country())

    @tool
    def get_pipeline_by_classification() -> dict[str, Any]:
        """Distribuye oportunidades abiertas por clasificación y separa ACV por moneda."""
        return recorder.record(
            "get_pipeline_by_classification",
            metrics_service.get_pipeline_by_classification(),
        )

    @tool
    def get_acv_by_currency() -> dict[str, Any]:
        """Entrega el ACV separado por moneda sin consolidarlo en un total multimoneda."""
        return recorder.record("get_acv_by_currency", metrics_service.get_acv_by_currency())

    @tool(args_schema=TVTInput)
    def get_opportunity_by_tvt(tvt: str) -> dict[str, Any]:
        """Busca una oportunidad puntual por su código TVT."""
        return recorder.record(
            "get_opportunity_by_tvt",
            metrics_service.get_opportunity_by_tvt(tvt),
        )

    @tool(args_schema=TVTInput)
    def get_products_by_tvt(tvt: str) -> dict[str, Any]:
        """Obtiene los productos asociados a un TVT puntual."""
        return recorder.record(
            "get_products_by_tvt",
            metrics_service.get_products_by_tvt(tvt),
        )

    tools = [
        get_pipeline_summary,
        get_pipeline_by_country,
        get_pipeline_by_classification,
        get_acv_by_currency,
        get_opportunity_by_tvt,
        get_products_by_tvt,
    ]
    model = model_factory.build_chat_model()
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )


def _extract_last_tool_call_name(result: dict[str, Any]) -> str | None:
    messages = result.get("messages")
    if not isinstance(messages, list):
        return None

    for message in reversed(messages):
        tool_calls = getattr(message, "tool_calls", None)
        if isinstance(tool_calls, list) and tool_calls:
            candidate = tool_calls[-1]
            if isinstance(candidate, dict):
                name = candidate.get("name")
                if isinstance(name, str) and name:
                    return name
    return None


class CommercialAgentService:
    def __init__(
        self,
        executor: AgentExecutor,
        response_writer: ResponseWriter,
        recorder: ToolExecutionRecorder,
    ) -> None:
        self._executor = executor
        self._response_writer = response_writer
        self._recorder = recorder

    def query(self, question: str) -> AgentQueryResponse:
        self._recorder.reset()
        result = self._executor.invoke(
            {
                "messages": [
                    {"role": "user", "content": question},
                ]
            }
        )
        answer = self._response_writer.write(result)
        payload = self._recorder.last_payload or {}
        warnings = payload.get("warnings")
        if not isinstance(warnings, list):
            warnings = []
        tool_used = self._recorder.last_tool_name or _extract_last_tool_call_name(result)
        return AgentQueryResponse(
            answer=answer,
            tool_used=tool_used,
            data_updated_at=payload.get("data_updated_at"),
            warnings=[str(warning) for warning in warnings],
        )
