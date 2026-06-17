from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from sales_assistant.config import resolve_project_path
from sales_assistant.ingestion.workbook_loader import parse_date_like, parse_decimal_like


@dataclass(frozen=True, slots=True)
class OpportunityRecord:
    id: str
    tvt: str | None
    name: str | None
    stage_name: str | None
    is_closed: bool
    is_won: bool
    close_date: date | None
    actual_close_date: date | None
    acv: float | None
    country: str | None
    classification: str | None
    sub_classification: str | None
    currency_iso_code: str | None
    owner_name: str | None
    account_name: str | None
    system_modstamp: datetime | None
    last_modified_date: datetime | None


@dataclass(frozen=True, slots=True)
class OpportunityItemRecord:
    id: str
    opportunity_id: str
    product_name: str | None
    product_code: str | None
    quantity: float | None
    unit_price: float | None
    total_price: float | None
    system_modstamp: datetime | None
    last_modified_date: datetime | None


@dataclass(frozen=True, slots=True)
class CuratedDataset:
    opportunities: tuple[OpportunityRecord, ...]
    opportunity_items: tuple[OpportunityItemRecord, ...]
    data_updated_at: datetime | None
    validation_summary: dict[str, Any]


class Repository(Protocol):
    def load_dataset(self) -> CuratedDataset: ...

    def healthcheck(self) -> bool: ...


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().casefold() in {"true", "1", "yes"}


def _normalize_date(value: Any) -> date | None:
    parsed = parse_date_like(value)
    return parsed.date() if parsed is not None else None


def _normalize_datetime(value: Any) -> datetime | None:
    return parse_date_like(value)


def _get_first_present(row: pd.Series, names: tuple[str, ...]) -> Any:
    for name in names:
        if name in row.index:
            return row[name]
    return None


class CsvCuratedSalesRepository:
    def __init__(self, curated_dir: str | Path) -> None:
        self._curated_dir = resolve_project_path(curated_dir)

    @property
    def curated_dir(self) -> Path:
        return self._curated_dir

    def load_dataset(self) -> CuratedDataset:
        opportunities_path = self._curated_dir / "opportunities.csv"
        items_path = self._curated_dir / "opportunity_items.csv"
        validation_path = self._curated_dir / "validation_summary.json"

        opportunities_frame = pd.read_csv(opportunities_path, dtype=object)
        items_frame = pd.read_csv(items_path, dtype=object)
        validation_summary: dict[str, Any] = {}
        if validation_path.exists():
            validation_summary = json.loads(validation_path.read_text(encoding="utf-8"))

        opportunities = tuple(self._build_opportunity_records(opportunities_frame))
        opportunity_items = tuple(self._build_opportunity_item_records(items_frame))
        data_updated_at = _normalize_datetime(validation_summary.get("data_updated_at"))

        if data_updated_at is None:
            candidate_datetimes = [
                record.system_modstamp
                for record in opportunities
                if record.system_modstamp is not None
            ]
            candidate_datetimes.extend(
                record.system_modstamp
                for record in opportunity_items
                if record.system_modstamp is not None
            )
            if candidate_datetimes:
                data_updated_at = max(candidate_datetimes)

        return CuratedDataset(
            opportunities=opportunities,
            opportunity_items=opportunity_items,
            data_updated_at=data_updated_at,
            validation_summary=validation_summary,
        )

    def healthcheck(self) -> bool:
        return (self._curated_dir / "opportunities.csv").exists() and (
            self._curated_dir / "opportunity_items.csv"
        ).exists()

    @staticmethod
    def _build_opportunity_records(frame: pd.DataFrame) -> list[OpportunityRecord]:
        records: list[OpportunityRecord] = []
        for _, row in frame.iterrows():
            records.append(
                OpportunityRecord(
                    id=str(_get_first_present(row, ("Id", "OpportunityId"))),
                    tvt=_normalize_text(_get_first_present(row, ("TVT__c", "Opportunity.TVT__c"))),
                    name=_normalize_text(_get_first_present(row, ("Name", "Opportunity.Name"))),
                    stage_name=_normalize_text(
                        _get_first_present(row, ("StageName", "Opportunity.StageName"))
                    ),
                    is_closed=_normalize_bool(_get_first_present(row, ("IsClosed",))),
                    is_won=_normalize_bool(_get_first_present(row, ("IsWon",))),
                    close_date=_normalize_date(
                        _get_first_present(row, ("CloseDate", "Opportunity.CloseDate"))
                    ),
                    actual_close_date=_normalize_date(
                        _get_first_present(
                            row,
                            (
                                "Data_de_Fechamento_Real__c",
                                "Opportunity.Data_de_Fechamento_Real__c",
                            ),
                        )
                    ),
                    acv=parse_decimal_like(
                        _get_first_present(row, ("ACV__c", "Opportunity.ACV__c"))
                    ),
                    country=_normalize_text(
                        _get_first_present(row, ("Pais__c", "Opportunity.Pais__c"))
                    ),
                    classification=_normalize_text(
                        _get_first_present(
                            row, ("Classificacao__c", "Opportunity.Classificacao__c")
                        )
                    ),
                    sub_classification=_normalize_text(
                        _get_first_present(
                            row,
                            (
                                "Sub_Classifica_o_BU_Opp__c",
                                "Opportunity.Sub_Classifica_o_BU_Opp__c",
                            ),
                        )
                    ),
                    currency_iso_code=_normalize_text(
                        _get_first_present(row, ("CurrencyIsoCode", "Opportunity.CurrencyIsoCode"))
                    ),
                    owner_name=_normalize_text(
                        _get_first_present(row, ("Owner.Name", "Opportunity.Owner.Name"))
                    ),
                    account_name=_normalize_text(
                        _get_first_present(row, ("Account.Name", "Opportunity.Account.Name"))
                    ),
                    system_modstamp=_normalize_datetime(
                        _get_first_present(row, ("SystemModstamp",))
                    ),
                    last_modified_date=_normalize_datetime(
                        _get_first_present(row, ("LastModifiedDate",))
                    ),
                )
            )
        return records

    @staticmethod
    def _build_opportunity_item_records(frame: pd.DataFrame) -> list[OpportunityItemRecord]:
        records: list[OpportunityItemRecord] = []
        for _, row in frame.iterrows():
            records.append(
                OpportunityItemRecord(
                    id=str(_get_first_present(row, ("Id",)))
                    if _get_first_present(row, ("Id",)) is not None
                    else str(_get_first_present(row, ("OpportunityLineItemId",))),
                    opportunity_id=str(_get_first_present(row, ("OpportunityId",))),
                    product_name=_normalize_text(_get_first_present(row, ("Product2.Name",))),
                    product_code=_normalize_text(_get_first_present(row, ("ProductCode",))),
                    quantity=parse_decimal_like(_get_first_present(row, ("Quantity",))),
                    unit_price=parse_decimal_like(_get_first_present(row, ("UnitPrice",))),
                    total_price=parse_decimal_like(_get_first_present(row, ("TotalPrice",))),
                    system_modstamp=_normalize_datetime(
                        _get_first_present(row, ("SystemModstamp",))
                    ),
                    last_modified_date=_normalize_datetime(
                        _get_first_present(row, ("LastModifiedDate",))
                    ),
                )
            )
        return records
