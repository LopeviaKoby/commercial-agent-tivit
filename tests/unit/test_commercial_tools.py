from __future__ import annotations

import json

import pandas as pd

from sales_assistant.business.commercial_tools import CommercialMetricsService
from sales_assistant.persistence.repository import CsvCuratedSalesRepository


def _write_curated_dataset(tmp_path) -> CsvCuratedSalesRepository:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Id": "006A",
                "TVT__c": "TVT-001",
                "Name": "Opportunity A",
                "StageName": "Pipeline",
                "IsClosed": False,
                "IsWon": False,
                "CloseDate": "2026-06-30",
                "Data_de_Fechamento_Real__c": None,
                "ACV__c": 100.0,
                "Pais__c": "Brasil",
                "Classificacao__c": "Crescimento",
                "Sub_Classifica_o_BU_Opp__c": "Cloud",
                "CurrencyIsoCode": "BRL",
                "Owner.Name": "Owner A",
                "Account.Name": "Account A",
                "SystemModstamp": "2026-06-16T10:00:00",
                "LastModifiedDate": "2026-06-16T10:00:00",
            },
            {
                "Id": "006B",
                "TVT__c": "TVT-002",
                "Name": "Opportunity B",
                "StageName": "Pipeline",
                "IsClosed": False,
                "IsWon": False,
                "CloseDate": "2026-07-01",
                "Data_de_Fechamento_Real__c": None,
                "ACV__c": 200.0,
                "Pais__c": "Peru",
                "Classificacao__c": "Renovacao",
                "Sub_Classifica_o_BU_Opp__c": "SAP",
                "CurrencyIsoCode": "PEN",
                "Owner.Name": "Owner B",
                "Account.Name": "Account B",
                "SystemModstamp": "2026-06-16T12:00:00",
                "LastModifiedDate": "2026-06-16T12:00:00",
            },
            {
                "Id": "006C",
                "TVT__c": "TVT-003",
                "Name": "Opportunity C",
                "StageName": "Pipeline",
                "IsClosed": False,
                "IsWon": False,
                "CloseDate": "2026-07-10",
                "Data_de_Fechamento_Real__c": None,
                "ACV__c": 50.0,
                "Pais__c": "Brasil",
                "Classificacao__c": "Crescimento",
                "Sub_Classifica_o_BU_Opp__c": "Cloud",
                "CurrencyIsoCode": "BRL",
                "Owner.Name": "Owner C",
                "Account.Name": "Account C",
                "SystemModstamp": "2026-06-16T13:00:00",
                "LastModifiedDate": "2026-06-16T13:00:00",
            },
        ]
    ).to_csv(curated_dir / "opportunities.csv", index=False)

    pd.DataFrame(
        [
            {
                "Id": "00k1",
                "OpportunityId": "006A",
                "Product2.Name": "Product 1",
                "ProductCode": "P1",
                "Quantity": 1,
                "UnitPrice": 100,
                "TotalPrice": 100,
                "SystemModstamp": "2026-06-16T10:30:00",
                "LastModifiedDate": "2026-06-16T10:30:00",
            },
            {
                "Id": "00k2",
                "OpportunityId": "006A",
                "Product2.Name": "Product 2",
                "ProductCode": "P2",
                "Quantity": 2,
                "UnitPrice": 50,
                "TotalPrice": 100,
                "SystemModstamp": "2026-06-16T10:35:00",
                "LastModifiedDate": "2026-06-16T10:35:00",
            },
        ]
    ).to_csv(curated_dir / "opportunity_items.csv", index=False)

    (curated_dir / "validation_summary.json").write_text(
        json.dumps({"data_updated_at": "2026-06-16T13:00:00"}, ensure_ascii=False),
        encoding="utf-8",
    )

    return CsvCuratedSalesRepository(curated_dir)


def test_pipeline_by_country_counts_unique_opportunities(tmp_path) -> None:
    service = CommercialMetricsService(repository=_write_curated_dataset(tmp_path))

    result = service.get_pipeline_by_country()

    brasil = next(row for row in result["rows"] if row["country"] == "Brasil")
    assert brasil["opportunity_count"] == 2
    assert brasil["acv_by_currency"] == [
        {"currency_iso_code": "BRL", "opportunity_count": 2, "acv": 150.0}
    ]


def test_pipeline_by_classification_separates_distribution(tmp_path) -> None:
    service = CommercialMetricsService(repository=_write_curated_dataset(tmp_path))

    result = service.get_pipeline_by_classification()

    crecimiento = next(row for row in result["rows"] if row["classification"] == "Crescimento")
    assert crecimiento["opportunity_count"] == 2


def test_acv_by_currency_never_merges_currencies(tmp_path) -> None:
    service = CommercialMetricsService(repository=_write_curated_dataset(tmp_path))

    result = service.get_acv_by_currency()

    assert result["rows"] == [
        {"currency_iso_code": "BRL", "opportunity_count": 2, "acv": 150.0},
        {"currency_iso_code": "PEN", "opportunity_count": 1, "acv": 200.0},
    ]
    assert "multimoneda" in result["warnings"][0]


def test_get_opportunity_by_tvt_reads_from_curated(tmp_path) -> None:
    service = CommercialMetricsService(repository=_write_curated_dataset(tmp_path))

    result = service.get_opportunity_by_tvt("TVT-001")

    assert result["source"] == "curated"
    assert result["opportunities"][0]["id"] == "006A"


def test_get_products_by_tvt_reads_product_lines(tmp_path) -> None:
    service = CommercialMetricsService(repository=_write_curated_dataset(tmp_path))

    result = service.get_products_by_tvt("TVT-001")

    assert result["source"] == "curated"
    assert len(result["products"]) == 2


def test_get_products_by_tvt_converts_nan_to_none_and_omits_empty_product_code(tmp_path) -> None:
    repository = _write_curated_dataset(tmp_path)
    pd.DataFrame(
        [
            {
                "Id": "00k9",
                "OpportunityId": "006A",
                "Product2.Name": "CYBER SECURITY | SOFTWARE",
                "ProductCode": float("nan"),
                "Quantity": 1,
                "UnitPrice": 1518.34,
                "TotalPrice": 1518.34,
                "SystemModstamp": "2026-06-16T10:30:00",
                "LastModifiedDate": "2026-06-16T10:30:00",
            }
        ]
    ).to_csv(repository.curated_dir / "opportunity_items.csv", index=False)

    service = CommercialMetricsService(repository=repository)
    result = service.get_products_by_tvt("TVT-001")

    product = result["products"][0]
    serialized = json.dumps(result, ensure_ascii=False)

    assert product["product_name"] == "CYBER SECURITY | SOFTWARE"
    assert "product_code" not in product
    assert "nan" not in serialized.casefold()


def test_serialize_opportunity_converts_nan_to_none() -> None:
    record = CsvCuratedSalesRepository._build_opportunity_records(
        pd.DataFrame(
            [
                {
                    "Id": "006A",
                    "TVT__c": float("nan"),
                    "Name": "Opportunity A",
                    "StageName": "Pipeline",
                    "IsClosed": False,
                    "IsWon": False,
                    "CloseDate": None,
                    "Data_de_Fechamento_Real__c": None,
                    "ACV__c": 100.0,
                    "Pais__c": "Brasil",
                    "Classificacao__c": "Crescimento",
                    "Sub_Classifica_o_BU_Opp__c": "Cloud",
                    "CurrencyIsoCode": "BRL",
                    "Owner.Name": "Owner A",
                    "Account.Name": "Account A",
                    "SystemModstamp": None,
                    "LastModifiedDate": None,
                }
            ]
        )
    )[0]

    payload = CommercialMetricsService._serialize_opportunity(record)

    assert payload["tvt"] is None
