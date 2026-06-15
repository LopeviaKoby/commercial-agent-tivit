from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm", ".csv"}
HEADER_SCAN_ROWS = 12
HEADER_KEYWORDS = (
    "acv",
    "budget",
    "status",
    "fase",
    "stage",
    "país",
    "pais",
    "country",
    "data",
    "date",
    "nome",
    "razão",
    "razao",
    "class",
    "lob",
    "bu",
    "partner",
    "parceiro",
    "tvt",
)
MONEY_KEYWORDS = (
    "acv",
    "reais",
    "revenue",
    "budget",
    "bud",
    "quota",
    "cotação",
    "cotacao",
    "valor",
    "amount",
    "total",
)
IDENTIFIER_KEYWORDS = ("id", "codigo", "código", "code", "cod", "tvt")


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def safe_str(value: Any) -> str:
    if is_missing(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value).strip()


def normalize_header(value: Any) -> str:
    text = safe_str(value)
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


def header_tokens(value: str) -> set[str]:
    normalized = normalize_header(value)
    if not normalized:
        return set()
    return {token for token in re.split(r"[^0-9A-Za-zÀ-ÿ]+", normalized) if token}


def parse_decimal_like(value: Any) -> float | None:
    if is_missing(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)

    text = safe_str(value)
    if not text:
        return None

    normalized = text.replace("\u00a0", "").replace(" ", "")
    normalized = normalized.replace("R$", "").replace("$", "")
    normalized = normalized.replace("%", "")
    normalized = normalized.replace("(", "-").replace(")", "")

    if "," in normalized and "." in normalized:
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
    elif "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")

    try:
        return float(normalized)
    except ValueError:
        return None


def parse_date_like(value: Any) -> datetime | None:
    if is_missing(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, datetime):
        return value

    text = safe_str(value)
    if not text:
        return None

    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def infer_value_type(values: list[Any]) -> str:
    sample = [value for value in values if not is_missing(value)]
    if not sample:
        return "empty"

    numeric_hits = sum(1 for value in sample if parse_decimal_like(value) is not None)
    date_hits = sum(1 for value in sample if parse_date_like(value) is not None)
    bool_hits = sum(1 for value in sample if isinstance(value, bool))
    total = len(sample)

    if bool_hits == total:
        return "boolean"
    if numeric_hits == total:
        as_numbers = [parse_decimal_like(value) for value in sample]
        if all(number is not None and number.is_integer() for number in as_numbers):
            return "integer"
        return "decimal"
    if date_hits == total:
        return "date"
    if numeric_hits / total >= 0.8:
        return "mostly_decimal"
    if date_hits / total >= 0.8:
        return "mostly_date"
    if numeric_hits > 0 or date_hits > 0:
        return "mixed"
    return "string"


def anonymize_value(value: Any) -> str:
    if is_missing(value):
        return "<empty>"

    if isinstance(value, bool):
        return str(value).lower()

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "<number>"

    parsed_date = parse_date_like(value)
    if parsed_date is not None:
        return parsed_date.date().isoformat()

    text = safe_str(value)
    if text.startswith("="):
        return "<formula>"

    if parse_decimal_like(text) is not None:
        return "<number>"

    if "@" in text:
        return "<email_like_text>"

    if re.fullmatch(r"[A-Za-z0-9\-_./]+", text):
        return f"<code_like:{len(text)}>"

    words = [segment for segment in re.split(r"\s+", text) if segment]
    if len(words) >= 2:
        return f"<text_words:{len(words)}>"
    return f"<text:{len(text)}>"


def header_keyword_score(values: list[str]) -> int:
    score = 0
    for value in values:
        lowered = value.casefold()
        if any(keyword in lowered for keyword in HEADER_KEYWORDS):
            score += 2
    return score


def detect_header_row(preview: pd.DataFrame) -> dict[str, Any]:
    best_row = 0
    best_score = float("-inf")
    header_values: list[str] = []

    scan_limit = min(HEADER_SCAN_ROWS, len(preview.index))
    for row_index in range(scan_limit):
        row_values = [safe_str(value) for value in preview.iloc[row_index].tolist()]
        non_empty = [value for value in row_values if value]
        if len(non_empty) < 2:
            score = -100.0 + row_index
        else:
            numeric_hits = sum(1 for value in non_empty if parse_decimal_like(value) is not None)
            unique_ratio = len({value.casefold() for value in non_empty}) / len(non_empty)
            alpha_hits = sum(1 for value in non_empty if re.search(r"[A-Za-zÀ-ÿ]", value))
            score = (
                len(non_empty) * 3
                + unique_ratio * 4
                + alpha_hits * 1.5
                + header_keyword_score(non_empty)
                - numeric_hits * 2.5
                - row_index * 0.4
            )
        if score > best_score:
            best_score = score
            best_row = row_index
            header_values = row_values

    return {
        "row_index_zero_based": best_row,
        "row_number_excel": best_row + 1,
        "score": round(best_score, 2),
        "values": header_values,
    }


def load_preview(path: Path, sheet_name: str | None = None) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(
            path,
            header=None,
            nrows=HEADER_SCAN_ROWS,
            dtype=object,
            encoding="utf-8-sig",
        )

    return pd.read_excel(
        path,
        sheet_name=sheet_name,
        header=None,
        nrows=HEADER_SCAN_ROWS,
        dtype=object,
        engine="openpyxl",
    )


def load_data_frame(path: Path, header_row: int, sheet_name: str | None = None) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(
            path,
            header=None,
            skiprows=header_row + 1,
            dtype=object,
            encoding="utf-8-sig",
        )
    else:
        frame = pd.read_excel(
            path,
            sheet_name=sheet_name,
            header=None,
            skiprows=header_row + 1,
            dtype=object,
            engine="openpyxl",
        )

    frame = frame.dropna(axis=1, how="all")
    frame.columns = list(range(frame.shape[1]))
    return frame


def load_tabular_sheet(
    path: Path,
    sheet_name: str | None = None,
    header_row: int | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    preview = load_preview(path, sheet_name=sheet_name)
    header_info = (
        detect_header_row(preview)
        if header_row is None
        else {
            "row_index_zero_based": header_row,
            "row_number_excel": header_row + 1,
            "score": None,
            "values": [safe_str(value) for value in preview.iloc[header_row].tolist()]
            if len(preview.index) > header_row
            else [],
        }
    )
    frame = load_data_frame(
        path,
        header_row=header_info["row_index_zero_based"],
        sheet_name=sheet_name,
    )
    headers = [
        safe_str(value) or f"unnamed_column_{index + 1}"
        for index, value in enumerate(header_info["values"][: frame.shape[1]])
    ]
    if len(headers) < frame.shape[1]:
        missing_headers = frame.shape[1] - len(headers)
        headers.extend(
            f"unnamed_column_{index + len(headers) + 1}" for index in range(missing_headers)
        )
    frame.columns = headers[: frame.shape[1]]
    frame = frame.dropna(axis=0, how="all").reset_index(drop=True)
    return frame, header_info


def repeated_headers(headers: list[str]) -> list[str]:
    counter = Counter(normalize_header(header) for header in headers if normalize_header(header))
    return sorted(header for header, count in counter.items() if count > 1)
