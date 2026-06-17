from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from typing import Any

import pandas as pd

from sales_assistant.ingestion.salesforce_cli_reader import SalesforceCliReader
from sales_assistant.persistence.repository import (
    CsvCuratedSalesRepository,
    OpportunityItemRecord,
    OpportunityRecord,
)


def _isoformat_or_none(value: object) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _clean_text(value: str | None) -> str:
    return value or "Sin dato"


def _normalize_tool_value(value: Any) -> Any:
    if value is None:
        return None
    return None if pd.isna(value) else value


class CommercialMetricsService:
    def __init__(
        self,
        repository: CsvCuratedSalesRepository,
        live_reader: SalesforceCliReader | None = None,
        live_fallback_enabled: bool = True,
    ) -> None:
        self._repository = repository
        self._live_reader = live_reader
        self._live_fallback_enabled = live_fallback_enabled

    def get_pipeline_summary(self) -> dict[str, Any]:
        dataset = self._repository.load_dataset()
        return {
            "tool_used": "get_pipeline_summary",
            "data_updated_at": _isoformat_or_none(dataset.data_updated_at),
            "warnings": [],
            "summary": {
                "open_opportunity_count": len(dataset.opportunities),
                "opportunity_item_count": len(dataset.opportunity_items),
                "countries_count": len(
                    {record.country for record in dataset.opportunities if record.country}
                ),
                "classifications_count": len(
                    {
                        record.classification
                        for record in dataset.opportunities
                        if record.classification
                    }
                ),
                "acv_by_currency": self._aggregate_acv_by_currency(dataset.opportunities),
            },
        }

    def get_pipeline_by_country(self) -> dict[str, Any]:
        dataset = self._repository.load_dataset()
        grouped: dict[str, list[OpportunityRecord]] = defaultdict(list)
        for record in dataset.opportunities:
            grouped[_clean_text(record.country)].append(record)

        rows = []
        for country, records in sorted(grouped.items()):
            rows.append(
                {
                    "country": country,
                    "opportunity_count": len(records),
                    "acv_by_currency": self._aggregate_acv_by_currency(records),
                }
            )

        return {
            "tool_used": "get_pipeline_by_country",
            "data_updated_at": _isoformat_or_none(dataset.data_updated_at),
            "warnings": [],
            "rows": rows,
        }

    def get_pipeline_by_classification(self) -> dict[str, Any]:
        dataset = self._repository.load_dataset()
        grouped: dict[str, list[OpportunityRecord]] = defaultdict(list)
        for record in dataset.opportunities:
            grouped[_clean_text(record.classification)].append(record)

        rows = []
        for classification, records in sorted(grouped.items()):
            rows.append(
                {
                    "classification": classification,
                    "opportunity_count": len(records),
                    "acv_by_currency": self._aggregate_acv_by_currency(records),
                }
            )

        return {
            "tool_used": "get_pipeline_by_classification",
            "data_updated_at": _isoformat_or_none(dataset.data_updated_at),
            "warnings": [],
            "rows": rows,
        }

    def get_acv_by_currency(self) -> dict[str, Any]:
        dataset = self._repository.load_dataset()
        return {
            "tool_used": "get_acv_by_currency",
            "data_updated_at": _isoformat_or_none(dataset.data_updated_at),
            "warnings": [
                "Los importes se entregan separados por moneda. No se calcula un total multimoneda."
            ],
            "rows": self._aggregate_acv_by_currency(dataset.opportunities),
        }

    def get_opportunity_by_tvt(self, tvt: str) -> dict[str, Any]:
        dataset = self._repository.load_dataset()
        warnings: list[str] = []
        matching = [record for record in dataset.opportunities if record.tvt == tvt]
        source = "curated"

        if not matching and self._live_reader is not None and self._live_fallback_enabled:
            source = "salesforce_live"
            warnings.append(
                "No se encontró el TVT en el snapshot curado; "
                "se consultó Salesforce en vivo para este TVT puntual."
            )
            matching = self._map_live_opportunities(
                self._live_reader.fetch_opportunity_by_tvt(tvt).records
            )

        return {
            "tool_used": "get_opportunity_by_tvt",
            "data_updated_at": _isoformat_or_none(dataset.data_updated_at),
            "warnings": warnings,
            "source": source,
            "opportunities": [self._serialize_opportunity(record) for record in matching],
        }

    def get_products_by_tvt(self, tvt: str) -> dict[str, Any]:
        dataset = self._repository.load_dataset()
        warnings: list[str] = []
        opportunity_ids = {record.id for record in dataset.opportunities if record.tvt == tvt}
        items = [
            item for item in dataset.opportunity_items if item.opportunity_id in opportunity_ids
        ]
        source = "curated"

        if not items and self._live_reader is not None and self._live_fallback_enabled:
            source = "salesforce_live"
            warnings.append(
                "No se encontraron productos para el TVT en el snapshot curado; "
                "se consultó Salesforce en vivo para este TVT puntual."
            )
            items = self._map_live_items(self._live_reader.fetch_products_by_tvt(tvt).records)

        return {
            "tool_used": "get_products_by_tvt",
            "data_updated_at": _isoformat_or_none(dataset.data_updated_at),
            "warnings": warnings,
            "source": source,
            "products": [self._serialize_item(item) for item in items],
        }

    @staticmethod
    def _aggregate_acv_by_currency(
        records: list[OpportunityRecord] | tuple[OpportunityRecord, ...],
    ) -> list[dict[str, Any]]:
        totals: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"opportunity_count": 0, "acv": 0.0}
        )
        for record in records:
            if record.currency_iso_code is None:
                continue
            bucket = totals[record.currency_iso_code]
            bucket["opportunity_count"] += 1
            if record.acv is not None:
                bucket["acv"] += record.acv

        rows = []
        for currency, values in sorted(totals.items()):
            rows.append(
                {
                    "currency_iso_code": currency,
                    "opportunity_count": values["opportunity_count"],
                    "acv": round(values["acv"], 2),
                }
            )
        return rows

    @staticmethod
    def _serialize_opportunity(record: OpportunityRecord) -> dict[str, Any]:
        payload = asdict(record)
        payload["close_date"] = _isoformat_or_none(record.close_date)
        payload["actual_close_date"] = _isoformat_or_none(record.actual_close_date)
        payload["system_modstamp"] = _isoformat_or_none(record.system_modstamp)
        payload["last_modified_date"] = _isoformat_or_none(record.last_modified_date)
        return {key: _normalize_tool_value(value) for key, value in payload.items()}

    @staticmethod
    def _serialize_item(record: OpportunityItemRecord) -> dict[str, Any]:
        payload = asdict(record)
        payload["system_modstamp"] = _isoformat_or_none(record.system_modstamp)
        payload["last_modified_date"] = _isoformat_or_none(record.last_modified_date)
        normalized = {key: _normalize_tool_value(value) for key, value in payload.items()}
        if normalized.get("product_code") is None:
            normalized.pop("product_code", None)
        return normalized

    @staticmethod
    def _map_live_opportunities(records: tuple[dict[str, Any], ...]) -> list[OpportunityRecord]:
        from sales_assistant.persistence.repository import CsvCuratedSalesRepository

        frame = pd.DataFrame.from_records(records)
        return CsvCuratedSalesRepository._build_opportunity_records(frame)

    @staticmethod
    def _map_live_items(records: tuple[dict[str, Any], ...]) -> list[OpportunityItemRecord]:
        from sales_assistant.persistence.repository import CsvCuratedSalesRepository

        frame = pd.DataFrame.from_records(records)
        return CsvCuratedSalesRepository._build_opportunity_item_records(frame)
