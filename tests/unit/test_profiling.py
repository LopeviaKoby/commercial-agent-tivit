import pandas as pd

from sales_assistant.business.profiling import (
    ABSOLUTE_MONEY_TOLERANCE,
    RELATIVE_MONEY_TOLERANCE,
    analyze_cross_file_relationships,
    analyze_group_column_behavior,
    mask_identifier,
    summarize_tvt_granularity,
    values_match_with_tolerance,
)
from sales_assistant.ingestion.workbook_loader import anonymize_value


def test_summarize_tvt_granularity_keeps_original_row_count() -> None:
    frame = pd.DataFrame({"TVT": [100, 100, 101, 102, 102]})

    result = summarize_tvt_granularity(frame, "TVT")

    assert result["row_count"] == 5
    assert result["distinct_tvt_count"] == 3
    assert result["single_row_tvt_count"] == 1
    assert result["multi_row_tvt_count"] == 2


def test_detects_constant_and_changing_columns_within_tvt() -> None:
    frame = pd.DataFrame(
        {
            "TVT": [1, 1, 2, 2],
            "Country": ["CL", "CL", "CO", "CO"],
            "ItemValue": [10, 11, 20, 20],
        }
    )

    result = analyze_group_column_behavior(
        frame,
        group_column="TVT",
        columns=["Country", "ItemValue"],
        column_kinds={"Country": "string", "ItemValue": "money"},
    )

    assert result["Country"]["constant_tvt_count"] == 2
    assert result["Country"]["changing_tvt_count"] == 0
    assert result["ItemValue"]["constant_tvt_count"] == 1
    assert result["ItemValue"]["changing_tvt_count"] == 1


def test_monetary_tolerance_comparison_accepts_small_rounding_difference() -> None:
    assert (
        values_match_with_tolerance(
            1000.0,
            1000.8,
            absolute_tolerance=ABSOLUTE_MONEY_TOLERANCE,
            relative_tolerance=RELATIVE_MONEY_TOLERANCE,
        )
        is True
    )
    assert values_match_with_tolerance(1000.0, 1005.0) is False


def test_cross_file_relationships_identify_many_pipe_to_one_when_pipe_repeats_tvt() -> None:
    pipe = pd.DataFrame({"TVT": [10, 10, 20]})
    ganadas = pd.DataFrame({"TVT": [10, 30]})

    result = analyze_cross_file_relationships(pipe, ganadas, "TVT")

    assert result["intersection_distinct_keys"] == 1
    assert result["observed_cardinality"] == "many_pipe_to_one_ganadas"
    assert result["pipe_match_ratio"] == 50.0


def test_anonymization_masks_sensitive_values() -> None:
    assert anonymize_value("Acme Corporation Chile") == "<text_words:3>"
    assert mask_identifier("123456", prefix="tvt").startswith("tvt_")
