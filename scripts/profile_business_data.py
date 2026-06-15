from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from sales_assistant.business.profiling import (
    ABSOLUTE_MONEY_TOLERANCE,
    RELATIVE_MONEY_TOLERANCE,
    analyze_cross_file_relationships,
    analyze_group_column_behavior,
    build_observable_dictionary_entries,
    coerce_date_series,
    coerce_numeric_series,
    evaluate_group_relationship,
    evaluate_row_formula,
    infer_monetary_candidates,
    profile_monetary_columns,
    profile_nulls,
    suggest_identifier_columns,
    summarize_tvt_granularity,
)
from sales_assistant.ingestion.excel_reader import ExcelReader
from sales_assistant.ingestion.workbook_loader import header_tokens, parse_decimal_like

ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "data" / "output"
INVENTORY_PATH = OUTPUT_DIR / "workbook_inventory.json"
QUALITY_PATH = OUTPUT_DIR / "data_quality_report.json"
BUSINESS_PROFILE_PATH = OUTPUT_DIR / "business_profile.json"
TVT_GRANULARITY_PATH = OUTPUT_DIR / "tvt_granularity_report.json"
CROSS_FILE_PATH = OUTPUT_DIR / "cross_file_relationships.json"
PENDING_VALIDATIONS_PATH = ROOT_DIR / "docs" / "pending_validations.md"
DATA_DICTIONARY_PATH = ROOT_DIR / "docs" / "data_dictionary.yaml"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_workbook(inventory: dict[str, Any], keyword: str) -> dict[str, Any]:
    lowered_keyword = keyword.casefold()
    for workbook in inventory["workbooks"]:
        if lowered_keyword in workbook["file_name"].casefold():
            return workbook
    raise ValueError(f"Workbook with keyword '{keyword}' was not found in inventory.")


def load_frame_from_inventory(
    workbook_entry: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    sheet_entry = workbook_entry["sheets"][0]
    path = ROOT_DIR / workbook_entry["file_path"]
    reader = ExcelReader()
    return reader.load_tabular_sheet(
        path,
        sheet_name=sheet_entry["sheet_name"],
        header_row=sheet_entry["possible_header_row"] - 1,
    )


def find_first_matching_column(frame: pd.DataFrame, token_options: list[set[str]]) -> str | None:
    for column in frame.columns:
        column_tokens = header_tokens(column)
        for option in token_options:
            if option.issubset(column_tokens):
                return column
    return None


def build_pipe_column_map(frame: pd.DataFrame) -> dict[str, str | None]:
    return {
        "tvt": "TVT" if "TVT" in frame.columns else None,
        "country": find_first_matching_column(frame, [{"país"}, {"pais"}, {"country"}]),
        "bu": find_first_matching_column(frame, [{"bu"}]),
        "lob": find_first_matching_column(frame, [{"lob"}]),
        "phase": find_first_matching_column(frame, [{"fase"}, {"stage"}]),
        "status": find_first_matching_column(frame, [{"status"}, {"negociação"}, {"negociacao"}]),
        "estimated_close_date": find_first_matching_column(
            frame,
            [{"data", "estimada"}, {"estimated", "closing"}],
        ),
        "actual_close_date": find_first_matching_column(frame, [{"data", "fechamento", "real"}]),
        "created_date": find_first_matching_column(
            frame,
            [{"data", "criacao"}, {"data", "criação"}],
        ),
        "acv": "ACV" if "ACV" in frame.columns else None,
        "acv_item_reais": ("ACV Item em Reais" if "ACV Item em Reais" in frame.columns else None),
        "acv_growth": ("ACV Crescimento Item" if "ACV Crescimento Item" in frame.columns else None),
        "acv_growth_reais": (
            "ACV Crescimento Item em Reais"
            if "ACV Crescimento Item em Reais" in frame.columns
            else None
        ),
        "acv_renewal": ("ACV Renovação Item" if "ACV Renovação Item" in frame.columns else None),
        "acv_renewal_reais": (
            "ACV Renovação Item em Reais"
            if "ACV Renovação Item em Reais" in frame.columns
            else None
        ),
        "item_classification": find_first_matching_column(
            frame,
            [
                {"sub", "classificacao", "bu", "item"},
                {"sub", "classificação", "bu", "item"},
            ],
        ),
        "product_name": find_first_matching_column(frame, [{"produto", "nome"}]),
        "opportunity_name": find_first_matching_column(frame, [{"nome", "oportunidade"}]),
    }


def build_ganadas_column_map(frame: pd.DataFrame) -> dict[str, str | None]:
    return {
        "tvt": "TVT" if "TVT" in frame.columns else None,
        "country": find_first_matching_column(frame, [{"país"}, {"pais"}, {"country"}]),
        "actual_close_date": find_first_matching_column(frame, [{"data", "fechamento", "real"}]),
        "status": find_first_matching_column(frame, [{"status"}]),
        "classification": find_first_matching_column(frame, [{"classificacao"}, {"classificação"}]),
        "opportunity_name": find_first_matching_column(frame, [{"nome", "oportunidade"}]),
        "sub_bu": find_first_matching_column(
            frame,
            [
                {"sub", "classificacao", "bu", "opp"},
                {"sub", "classificação", "bu", "opp"},
            ],
        ),
        "acv_growth": (
            "ACV Crescimento Cotação" if "ACV Crescimento Cotação" in frame.columns else None
        ),
        "acv_growth_reais": "ACV Crescimento Cotação em Reais"
        if "ACV Crescimento Cotação em Reais" in frame.columns
        else None,
        "acv_renewal": (
            "ACV Renovação Cotação" if "ACV Renovação Cotação" in frame.columns else None
        ),
        "acv_renewal_reais": "ACV Renovação Cotação em Reais"
        if "ACV Renovação Cotação em Reais" in frame.columns
        else None,
    }


def monetary_kind_map(frame: pd.DataFrame) -> dict[str, str]:
    kind_map: dict[str, str] = {}
    for column in frame.columns:
        if column in infer_monetary_candidates(list(frame.columns)):
            kind_map[column] = "money"
        elif "data" in header_tokens(column):
            kind_map[column] = "date"
        else:
            kind_map[column] = "string"
    return kind_map


def summarize_date_column(series: pd.Series) -> dict[str, Any]:
    parsed = coerce_date_series(series)
    valid_dates = [value for value in parsed.tolist() if value is not None]
    invalid_count = int(series.notna().sum() - len(valid_dates))
    if not valid_dates:
        return {
            "non_null_count": int(series.notna().sum()),
            "invalid_date_count": invalid_count,
            "min_date": None,
            "max_date": None,
        }
    return {
        "non_null_count": int(series.notna().sum()),
        "invalid_date_count": invalid_count,
        "min_date": min(valid_dates).date().isoformat(),
        "max_date": max(valid_dates).date().isoformat(),
    }


def summarize_pipe(
    frame: pd.DataFrame,
    column_map: dict[str, str | None],
) -> tuple[dict[str, Any], dict[str, Any]]:
    tvt_column = column_map["tvt"]
    assert tvt_column is not None

    special_columns = [
        column_map["country"],
        column_map["bu"],
        column_map["lob"],
        column_map["phase"],
        column_map["status"],
        column_map["estimated_close_date"],
        column_map["actual_close_date"],
        column_map["created_date"],
        column_map["acv"],
        column_map["acv_item_reais"],
        column_map["acv_growth"],
        column_map["acv_growth_reais"],
        column_map["acv_renewal"],
        column_map["acv_renewal_reais"],
        column_map["item_classification"],
        column_map["product_name"],
        column_map["opportunity_name"],
    ]
    observed_special_columns = [column for column in special_columns if column]
    column_behavior = analyze_group_column_behavior(
        frame,
        group_column=tvt_column,
        columns=observed_special_columns,
        column_kinds=monetary_kind_map(frame),
    )

    acv_relation = (
        evaluate_group_relationship(
            frame,
            tvt_column,
            column_map["acv"],
            column_map["acv_item_reais"],
        )
        if column_map["acv"] and column_map["acv_item_reais"]
        else {}
    )
    growth_plus_renewal_equals_acv = (
        evaluate_row_formula(
            frame,
            [column_map["acv_growth"], column_map["acv_renewal"]],
            column_map["acv"],
        )
        if column_map["acv_growth"] and column_map["acv_renewal"] and column_map["acv"]
        else {}
    )
    growth_plus_renewal_reais_equals_item = (
        evaluate_row_formula(
            frame,
            [column_map["acv_growth_reais"], column_map["acv_renewal_reais"]],
            column_map["acv_item_reais"],
        )
        if column_map["acv_growth_reais"]
        and column_map["acv_renewal_reais"]
        and column_map["acv_item_reais"]
        else {}
    )

    repeated_behavior = {
        column: value
        for column, value in column_behavior.items()
        if value["changing_tvt_count"] > 0 or value["constant_tvt_count"] > 0
    }

    hypothesis = {
        "opportunity_level_columns": [
            column
            for column in [
                column_map["country"],
                column_map["bu"],
                column_map["phase"],
                column_map["status"],
                column_map["estimated_close_date"],
                column_map["actual_close_date"],
                column_map["created_date"],
            ]
            if column and column_behavior.get(column, {}).get("constant_tvt_percentage", 0) >= 80
        ],
        "item_level_columns": [
            column
            for column in [
                column_map["product_name"],
                column_map["item_classification"],
                column_map["acv_growth"],
                column_map["acv_growth_reais"],
                column_map["acv_renewal"],
                column_map["acv_renewal_reais"],
                column_map["acv_item_reais"],
            ]
            if column and column_behavior.get(column, {}).get("changing_tvt_percentage", 0) > 5
        ],
    }

    pipe_profile = {
        "tvt_granularity": summarize_tvt_granularity(frame, tvt_column),
        "null_percentages": profile_nulls(frame),
        "possible_identifier_columns": suggest_identifier_columns(frame),
        "monetary_profiles": profile_monetary_columns(
            frame,
            [
                column
                for column in infer_monetary_candidates(list(frame.columns))
                if column in frame.columns
            ],
        ),
        "column_behavior_within_repeated_tvt": repeated_behavior,
        "amount_relationships": {
            "acv_constant_within_tvt": column_behavior.get(column_map["acv"], {}),
            "acv_sum_item_reais_vs_acv": acv_relation,
            "growth_plus_renewal_equals_acv": growth_plus_renewal_equals_acv,
            "growth_plus_renewal_reais_equals_item_reais": growth_plus_renewal_reais_equals_item,
            "tolerance": {
                "absolute_brl": ABSOLUTE_MONEY_TOLERANCE,
                "relative_ratio": RELATIVE_MONEY_TOLERANCE,
            },
        },
        "granularity_hypothesis": hypothesis,
        "observed_requested_columns": {
            key: value if value is not None else "not_observed" for key, value in column_map.items()
        },
        "exact_duplicate_rows": int(frame.astype(str).duplicated().sum()),
    }

    dictionary_behavior = {
        column: {
            "constant_tvt_percentage": value["constant_tvt_percentage"],
            "changing_tvt_percentage": value["changing_tvt_percentage"],
            "avg_distinct_values_per_tvt": value["avg_distinct_values_per_tvt"],
            "status": "observed",
        }
        for column, value in repeated_behavior.items()
    }
    return pipe_profile, dictionary_behavior


def apparent_currency_summary(
    frame: pd.DataFrame,
    local_column: str,
    reais_column: str,
) -> dict[str, Any]:
    ratios: list[float] = []
    for _, row in frame.iterrows():
        local_value = parse_decimal_like(row[local_column])
        reais_value = parse_decimal_like(row[reais_column])
        if local_value in (None, 0) or reais_value in (None, 0):
            continue
        ratios.append(local_value / reais_value)
    return {
        "comparable_rows": len(ratios),
        "ratio_mean_local_div_reais": round(sum(ratios) / len(ratios), 4) if ratios else None,
        "ratio_min_local_div_reais": round(min(ratios), 4) if ratios else None,
        "ratio_max_local_div_reais": round(max(ratios), 4) if ratios else None,
    }


def summarize_ganadas(frame: pd.DataFrame, column_map: dict[str, str | None]) -> dict[str, Any]:
    tvt_column = column_map["tvt"]
    possible_identifiers = suggest_identifier_columns(frame)

    growth_renewal_profile = {}
    if (
        column_map["acv_growth"]
        and column_map["acv_renewal"]
        and column_map["acv_growth_reais"]
        and column_map["acv_renewal_reais"]
    ):
        growth = coerce_numeric_series(frame[column_map["acv_growth"]])
        renewal = coerce_numeric_series(frame[column_map["acv_renewal"]])
        growth_reais = coerce_numeric_series(frame[column_map["acv_growth_reais"]])
        renewal_reais = coerce_numeric_series(frame[column_map["acv_renewal_reais"]])
        growth_renewal_profile = {
            "rows_with_growth_positive": int((growth.fillna(0) > 0).sum()),
            "rows_with_renewal_positive": int((renewal.fillna(0) > 0).sum()),
            "rows_with_both_positive": int(
                ((growth.fillna(0) > 0) & (renewal.fillna(0) > 0)).sum()
            ),
            "derived_totals": {
                "sum_growth_plus_renewal": round(
                    float(growth.fillna(0).sum() + renewal.fillna(0).sum()),
                    4,
                ),
                "sum_growth_plus_renewal_reais": round(
                    float(growth_reais.fillna(0).sum() + renewal_reais.fillna(0).sum()),
                    4,
                ),
            },
            "apparent_currency_without_suffix": apparent_currency_summary(
                frame,
                column_map["acv_growth"],
                column_map["acv_growth_reais"],
            ),
        }

    date_profile = {}
    if column_map["actual_close_date"]:
        date_profile[column_map["actual_close_date"]] = summarize_date_column(
            frame[column_map["actual_close_date"]]
        )

    duplicate_count = int(frame[tvt_column].dropna().duplicated().sum()) if tvt_column else 0
    return {
        "record_count": int(len(frame)),
        "possible_identifier_columns": possible_identifiers,
        "tvt_uniqueness": {
            "column": tvt_column,
            "distinct_count": int(frame[tvt_column].dropna().nunique()) if tvt_column else 0,
            "duplicate_count": duplicate_count,
            "is_unique": bool(duplicate_count == 0) if tvt_column else False,
        },
        "null_percentages": profile_nulls(frame),
        "date_profiles": date_profile,
        "monetary_profiles": profile_monetary_columns(
            frame,
            [
                column
                for column in infer_monetary_candidates(list(frame.columns))
                if column in frame.columns
            ],
        ),
        "growth_and_renewal_profile": growth_renewal_profile,
        "observed_requested_columns": {
            key: value if value is not None else "not_observed" for key, value in column_map.items()
        },
    }


def build_questions(cross_file_relationships: dict[str, Any]) -> list[str]:
    relationship_tail = (
        f"12. Si no hay intersección de `TVT` entre archivos "
        f"({cross_file_relationships['intersection_distinct_keys']} coincidencias), "
        "¿qué llave alternativa debería evaluarse para relacionarlos?"
    )
    return [
        "1. ¿Qué representa exactamente `TVT`: oportunidad, transacción, "
        "ítem comercial o identificador técnico de otro sistema?",
        "2. ¿Qué representa una fila en `Previa mayo - Pipe.xlsx`: una oportunidad "
        "completa o un ítem/subcomponente de oportunidad?",
        "3. ¿Cuál es la diferencia operativa entre `ACV` y `ACV Item em Reais` en Pipe?",
        "4. ¿Cuando un `TVT` aparece en varias filas, `ACV` debe repetirse por cada ítem "
        "o debería mantenerse solo una vez por oportunidad?",
        "5. ¿`ACV Crescimento Item` y `ACV Renovação Item` son componentes aditivos "
        "que deben reconciliar contra `ACV`?",
        "6. ¿Qué campo debe usarse para sumar pipeline sin doble conteo: `ACV`, "
        "`ACV Item em Reais` u otro campo no presente en estos extractos?",
        "7. ¿Qué columnas ya están convertidas a BRL/Reais y cuáles siguen "
        "en moneda de cotación/origen?",
        "8. ¿Cuál es la relación esperada entre los extractos `Pipe` y `Ganadas` "
        "si hoy no comparten ningún `TVT` observado?",
        "9. ¿Las 55 filas duplicadas exactas en Pipe deben eliminarse, "
        "consolidarse o conservarse por trazabilidad?",
        "10. ¿Qué significa que `Status da Negociação` esté vacío en la mayoría de filas de Pipe?",
        "11. ¿`Sub Classificação BU Item` y `Sub Classificação BU Opp` "
        "son dimensiones comparables entre archivos o conceptos distintos?",
        relationship_tail,
    ]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_dictionary_yaml(entries: list[dict[str, Any]]) -> None:
    lines = ["version: 1", "status: observed", "fields:"]
    for entry in entries:
        lines.append(f'  - source_file: "{entry["source_file"]}"')
        lines.append(f'    source_sheet: "{entry["source_sheet"]}"')
        lines.append(f'    original_name: "{entry["original_name"]}"')
        lines.append(f'    normalized_name: "{entry["normalized_name"]}"')
        lines.append(f'    type: "{entry["type"]}"')
        lines.append(f"    null_percentage: {entry['null_percentage']}")
        samples = ", ".join(f'"{sample}"' for sample in entry["sample_values"])
        lines.append(f"    sample_values: [{samples}]")
        behavior = entry["behavior_within_tvt"]
        if isinstance(behavior, dict):
            lines.append("    behavior_within_tvt:")
            for key, value in behavior.items():
                lines.append(f"      {key}: {json.dumps(value, ensure_ascii=False)}")
        else:
            lines.append(f'    behavior_within_tvt: "{behavior}"')
        lines.append(f'    validation_status: "{entry["validation_status"]}"')
    DATA_DICTIONARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_pending_validations(questions: list[str]) -> None:
    lines = ["# Validaciones pendientes", "", "Preguntas priorizadas para el operario:", ""]
    lines.extend(f"- {question}" for question in questions[:12])
    PENDING_VALIDATIONS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    inventory = read_json(INVENTORY_PATH)
    _quality_report = read_json(QUALITY_PATH)

    pipe_entry = find_workbook(inventory, "Pipe")
    ganadas_entry = find_workbook(inventory, "Ganadas")

    pipe_frame, _ = load_frame_from_inventory(pipe_entry)
    ganadas_frame, _ = load_frame_from_inventory(ganadas_entry)

    pipe_column_map = build_pipe_column_map(pipe_frame)
    ganadas_column_map = build_ganadas_column_map(ganadas_frame)

    pipe_profile, dictionary_behavior = summarize_pipe(pipe_frame, pipe_column_map)
    ganadas_profile = summarize_ganadas(ganadas_frame, ganadas_column_map)
    cross_file_relationships = analyze_cross_file_relationships(
        pipe_frame,
        ganadas_frame,
        key_column="TVT",
    )

    questions = build_questions(cross_file_relationships)

    business_profile = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "tolerance": {
            "absolute_brl": ABSOLUTE_MONEY_TOLERANCE,
            "relative_ratio": RELATIVE_MONEY_TOLERANCE,
        },
        "pipe": pipe_profile,
        "ganadas": ganadas_profile,
        "cross_file_relationships": cross_file_relationships,
        "questions_for_operator": questions,
        "potential_metrics_viability": [
            {
                "metric": "count_distinct_tvt_pipe",
                "status": "viable_observed",
                "reason": "Distinct TVT can be counted without summing monetary fields.",
            },
            {
                "metric": "ganadas_total_by_unique_tvt",
                "status": "potentially_viable",
                "reason": "Ganadas shows unique TVT, but currency semantics still need validation.",
            },
            {
                "metric": "pipeline_value_from_pipe",
                "status": "blocked_pending_validation",
                "reason": (
                    "Pipe has repeated TVT and ambiguous ACV vs item-level fields, "
                    "so sums may double count."
                ),
            },
        ],
    }

    write_json(BUSINESS_PROFILE_PATH, business_profile)
    write_json(TVT_GRANULARITY_PATH, pipe_profile["tvt_granularity"])
    write_json(CROSS_FILE_PATH, cross_file_relationships)
    dictionary_entries = build_observable_dictionary_entries(
        pipe_entry["file_name"],
        pipe_entry["sheets"][0]["sheet_name"],
        pipe_frame,
        within_tvt_behavior=dictionary_behavior,
    ) + build_observable_dictionary_entries(
        ganadas_entry["file_name"],
        ganadas_entry["sheets"][0]["sheet_name"],
        ganadas_frame,
    )
    write_dictionary_yaml(dictionary_entries)
    write_pending_validations(questions)

    print(f"Business profile written to {BUSINESS_PROFILE_PATH}")
    print(f"TVT granularity report written to {TVT_GRANULARITY_PATH}")
    print(f"Cross-file relationships written to {CROSS_FILE_PATH}")


if __name__ == "__main__":
    main()
