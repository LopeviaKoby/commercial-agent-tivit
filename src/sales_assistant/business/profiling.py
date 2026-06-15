from __future__ import annotations

import hashlib
import math
import statistics
import unicodedata
from collections import Counter
from typing import Any

import pandas as pd

from sales_assistant.ingestion.workbook_loader import (
    IDENTIFIER_KEYWORDS,
    MONEY_KEYWORDS,
    anonymize_value,
    header_tokens,
    is_missing,
    parse_date_like,
    parse_decimal_like,
    safe_str,
)

ABSOLUTE_MONEY_TOLERANCE = 1.0
RELATIVE_MONEY_TOLERANCE = 0.001


def normalize_technical_name(value: str) -> str:
    value = value.replace("%", " percent ")
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    lowered = ascii_value.casefold()
    cleaned = "".join(character if character.isalnum() else "_" for character in lowered)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


def mask_identifier(value: Any, prefix: str = "id") -> str:
    raw = safe_str(value)
    if not raw:
        return f"{prefix}_empty"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{digest}"


def coerce_numeric_series(series: pd.Series) -> pd.Series:
    return series.map(parse_decimal_like, na_action="ignore").astype("float64")


def coerce_date_series(series: pd.Series) -> pd.Series:
    return pd.Series([parse_date_like(value) for value in series], index=series.index, dtype=object)


def normalize_group_value(value: Any, column_kind: str = "string") -> str | None:
    if is_missing(value):
        return None
    if column_kind == "money":
        parsed = parse_decimal_like(value)
        if parsed is None:
            return safe_str(value)
        return f"{parsed:.6f}"
    if column_kind == "date":
        parsed = parse_date_like(value)
        if parsed is None:
            return safe_str(value)
        return parsed.date().isoformat()
    return safe_str(value)


def values_match_with_tolerance(
    left: float | None,
    right: float | None,
    absolute_tolerance: float = ABSOLUTE_MONEY_TOLERANCE,
    relative_tolerance: float = RELATIVE_MONEY_TOLERANCE,
) -> bool:
    if left is None or right is None:
        return False
    return math.isclose(
        left,
        right,
        abs_tol=absolute_tolerance,
        rel_tol=relative_tolerance,
    )


def summarize_tvt_granularity(frame: pd.DataFrame, tvt_column: str) -> dict[str, Any]:
    tvt_series = frame[tvt_column]
    non_null = tvt_series.dropna()
    counts = non_null.value_counts(dropna=True).sort_values(ascending=False)
    count_values = counts.tolist()
    distribution = Counter(count_values)

    return {
        "row_count": int(len(frame)),
        "distinct_tvt_count": int(non_null.nunique(dropna=True)),
        "null_tvt_rows": int(tvt_series.isna().sum()),
        "rows_per_tvt_distribution": {
            str(key): int(value) for key, value in sorted(distribution.items())
        },
        "rows_per_tvt_mean": (
            round(float(statistics.mean(count_values)), 4) if count_values else 0.0
        ),
        "rows_per_tvt_median": float(statistics.median(count_values)) if count_values else 0.0,
        "rows_per_tvt_p95": float(pd.Series(count_values).quantile(0.95)) if count_values else 0.0,
        "rows_per_tvt_max": int(max(count_values)) if count_values else 0,
        "top_20_tvt_by_row_count": [
            {
                "tvt": mask_identifier(index, prefix="tvt"),
                "row_count": int(value),
            }
            for index, value in counts.head(20).items()
        ],
        "single_row_tvt_count": int((counts == 1).sum()),
        "multi_row_tvt_count": int((counts > 1).sum()),
    }


def analyze_group_column_behavior(
    frame: pd.DataFrame,
    group_column: str,
    columns: list[str],
    column_kinds: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    repeated_frame = frame[frame[group_column].notna()].copy()
    repeated_frame["_group_size"] = repeated_frame.groupby(group_column)[group_column].transform(
        "size"
    )
    repeated_frame = repeated_frame[repeated_frame["_group_size"] > 1].drop(columns="_group_size")

    results: dict[str, dict[str, Any]] = {}
    if repeated_frame.empty:
        return results

    grouped = repeated_frame.groupby(group_column, dropna=True, sort=False)
    repeated_group_count = grouped.ngroups

    for column in columns:
        column_kind = (column_kinds or {}).get(column, "string")
        distinct_counts: list[int] = []
        constant_count = 0
        changing_count = 0
        all_missing_count = 0

        for _, group in grouped:
            normalized_values = [
                normalize_group_value(value, column_kind=column_kind)
                for value in group[column].tolist()
            ]
            present_values = [value for value in normalized_values if value is not None]
            distinct_value_count = len(set(present_values))
            distinct_counts.append(distinct_value_count)
            if not present_values:
                all_missing_count += 1
            elif distinct_value_count <= 1:
                constant_count += 1
            else:
                changing_count += 1

        results[column] = {
            "repeated_tvt_groups": repeated_group_count,
            "constant_tvt_count": constant_count,
            "changing_tvt_count": changing_count,
            "all_missing_tvt_count": all_missing_count,
            "constant_tvt_percentage": round(constant_count / repeated_group_count * 100, 2),
            "changing_tvt_percentage": round(changing_count / repeated_group_count * 100, 2),
            "avg_distinct_values_per_tvt": round(float(statistics.mean(distinct_counts)), 4),
            "max_distinct_values_per_tvt": int(max(distinct_counts)) if distinct_counts else 0,
        }

    return results


def evaluate_group_relationship(
    frame: pd.DataFrame,
    group_column: str,
    left_column: str,
    right_column: str,
    absolute_tolerance: float = ABSOLUTE_MONEY_TOLERANCE,
    relative_tolerance: float = RELATIVE_MONEY_TOLERANCE,
) -> dict[str, Any]:
    comparable_groups = 0
    matching_groups = 0
    differing_groups = 0
    rounded_difference_matches = 0
    samples: list[dict[str, Any]] = []

    grouped = frame[frame[group_column].notna()].groupby(group_column, dropna=True)
    for group_value, group in grouped:
        left_values = [parse_decimal_like(value) for value in group[left_column].tolist()]
        right_values = [parse_decimal_like(value) for value in group[right_column].tolist()]
        left_values = [value for value in left_values if value is not None]
        right_values = [value for value in right_values if value is not None]
        if not left_values or not right_values:
            continue

        left_reference = left_values[0] if len(set(left_values)) == 1 else None
        right_sum = sum(right_values)
        if left_reference is None:
            continue

        comparable_groups += 1
        if values_match_with_tolerance(
            left_reference,
            right_sum,
            absolute_tolerance=absolute_tolerance,
            relative_tolerance=relative_tolerance,
        ):
            matching_groups += 1
            if round(left_reference, 0) == round(right_sum, 0):
                rounded_difference_matches += 1
        else:
            differing_groups += 1
            if len(samples) < 5:
                samples.append(
                    {
                        "tvt": mask_identifier(group_value, prefix="tvt"),
                        "left_reference": round(left_reference, 4),
                        "right_sum": round(right_sum, 4),
                        "difference": round(right_sum - left_reference, 4),
                    }
                )

    return {
        "comparable_tvt_count": comparable_groups,
        "matching_tvt_count": matching_groups,
        "differing_tvt_count": differing_groups,
        "matching_tvt_percentage": round(matching_groups / comparable_groups * 100, 2)
        if comparable_groups
        else 0.0,
        "rounded_match_count": rounded_difference_matches,
        "difference_samples": samples,
        "absolute_tolerance": absolute_tolerance,
        "relative_tolerance": relative_tolerance,
    }


def evaluate_row_formula(
    frame: pd.DataFrame,
    left_columns: list[str],
    right_column: str,
    absolute_tolerance: float = ABSOLUTE_MONEY_TOLERANCE,
    relative_tolerance: float = RELATIVE_MONEY_TOLERANCE,
) -> dict[str, Any]:
    comparable_rows = 0
    matching_rows = 0

    for _, row in frame.iterrows():
        left_values = [parse_decimal_like(row[column]) for column in left_columns]
        right_value = parse_decimal_like(row[right_column])
        if right_value is None or any(value is None for value in left_values):
            continue
        comparable_rows += 1
        if values_match_with_tolerance(
            sum(value for value in left_values if value is not None),
            right_value,
            absolute_tolerance=absolute_tolerance,
            relative_tolerance=relative_tolerance,
        ):
            matching_rows += 1

    return {
        "comparable_row_count": comparable_rows,
        "matching_row_count": matching_rows,
        "matching_row_percentage": round(matching_rows / comparable_rows * 100, 2)
        if comparable_rows
        else 0.0,
        "absolute_tolerance": absolute_tolerance,
        "relative_tolerance": relative_tolerance,
    }


def profile_monetary_columns(frame: pd.DataFrame, columns: list[str]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for column in columns:
        numeric_values = [parse_decimal_like(value) for value in frame[column].tolist()]
        numeric_values = [value for value in numeric_values if value is not None]
        positives = [value for value in numeric_values if value > 0]
        zeros = [value for value in numeric_values if value == 0]
        negatives = [value for value in numeric_values if value < 0]
        results[column] = {
            "non_null_count": len(numeric_values),
            "positive_count": len(positives),
            "zero_count": len(zeros),
            "negative_count": len(negatives),
            "sum": round(sum(numeric_values), 4) if numeric_values else 0.0,
            "max": round(max(numeric_values), 4) if numeric_values else None,
            "min": round(min(numeric_values), 4) if numeric_values else None,
            "mean": (round(float(statistics.mean(numeric_values)), 4) if numeric_values else None),
            "median": (
                round(float(statistics.median(numeric_values)), 4) if numeric_values else None
            ),
        }
    return results


def suggest_identifier_columns(frame: pd.DataFrame) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for column in frame.columns:
        non_null_count = int(frame[column].notna().sum())
        if non_null_count == 0:
            continue
        distinct_count = int(frame[column].dropna().astype(str).nunique())
        tokens = header_tokens(column)
        unique_ratio = distinct_count / non_null_count
        if any(keyword in tokens for keyword in IDENTIFIER_KEYWORDS) or unique_ratio >= 0.95:
            suggestions.append(
                {
                    "column": column,
                    "non_null_count": non_null_count,
                    "distinct_count": distinct_count,
                    "uniqueness_ratio": round(unique_ratio, 4),
                }
            )
    return suggestions


def profile_nulls(frame: pd.DataFrame) -> dict[str, float]:
    return {
        column: (
            round(float(frame[column].isna().sum() / len(frame) * 100), 2) if len(frame) else 100.0
        )
        for column in frame.columns
    }


def analyze_cross_file_relationships(
    pipe_frame: pd.DataFrame,
    ganadas_frame: pd.DataFrame,
    key_column: str,
) -> dict[str, Any]:
    pipe_keys = pipe_frame[key_column].dropna().astype(str)
    ganadas_keys = ganadas_frame[key_column].dropna().astype(str)

    pipe_set = set(pipe_keys)
    ganadas_set = set(ganadas_keys)
    intersection = pipe_set & ganadas_set
    pipe_unique = len(pipe_set)
    ganadas_unique = len(ganadas_set)

    pipe_duplicates = int(pipe_keys.duplicated().sum())
    ganadas_duplicates = int(ganadas_keys.duplicated().sum())
    if pipe_duplicates == 0 and ganadas_duplicates == 0:
        cardinality = "one_to_one"
    elif pipe_duplicates > 0 and ganadas_duplicates == 0:
        cardinality = "many_pipe_to_one_ganadas"
    elif pipe_duplicates == 0 and ganadas_duplicates > 0:
        cardinality = "one_pipe_to_many_ganadas"
    else:
        cardinality = "many_to_many"

    return {
        "key_column": key_column,
        "pipe_distinct_keys": pipe_unique,
        "ganadas_distinct_keys": ganadas_unique,
        "intersection_distinct_keys": len(intersection),
        "pipe_only_distinct_keys": pipe_unique - len(intersection),
        "ganadas_only_distinct_keys": ganadas_unique - len(intersection),
        "pipe_match_ratio": round(len(intersection) / pipe_unique * 100, 2) if pipe_unique else 0.0,
        "ganadas_match_ratio": round(len(intersection) / ganadas_unique * 100, 2)
        if ganadas_unique
        else 0.0,
        "observed_cardinality": cardinality,
        "cardinality_validation_safe": len(intersection) > 0
        and cardinality
        in {
            "one_to_one",
            "many_pipe_to_one_ganadas",
        },
        "relationship_is_safe": len(intersection) > 0 and cardinality in {"one_to_one"},
        "match_samples": [
            mask_identifier(value, prefix="tvt") for value in sorted(intersection)[:10]
        ],
        "relationship_warning": (
            "No shared TVT values were observed between Pipe and Ganadas."
            if not intersection
            else "Shared TVT values exist; validate business meaning before merging."
        ),
    }


def build_observable_dictionary_entries(
    file_name: str,
    sheet_name: str,
    frame: pd.DataFrame,
    within_tvt_behavior: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for column in frame.columns:
        values = frame[column].tolist()
        non_null_values = [value for value in values if not is_missing(value)]
        inferred_type = "string"
        if non_null_values:
            numeric_ratio = sum(
                parse_decimal_like(value) is not None for value in non_null_values
            ) / len(non_null_values)
            date_ratio = sum(parse_date_like(value) is not None for value in non_null_values) / len(
                non_null_values
            )
            if date_ratio >= 0.8:
                inferred_type = "date"
            elif numeric_ratio == 1:
                inferred_type = "decimal"
            elif numeric_ratio >= 0.8:
                inferred_type = "mostly_decimal"

        entries.append(
            {
                "source_file": file_name,
                "source_sheet": sheet_name,
                "original_name": column,
                "normalized_name": normalize_technical_name(column),
                "type": inferred_type,
                "null_percentage": (
                    round((len(values) - len(non_null_values)) / len(values) * 100, 2)
                    if values
                    else 100.0
                ),
                "sample_values": [anonymize_value(value) for value in non_null_values[:3]],
                "behavior_within_tvt": (within_tvt_behavior or {}).get(column, "pending"),
                "validation_status": "observed",
            }
        )
    return entries


def infer_monetary_candidates(columns: list[str]) -> list[str]:
    candidates = []
    for column in columns:
        if any(keyword in header_tokens(column) for keyword in MONEY_KEYWORDS):
            candidates.append(column)
    return candidates
