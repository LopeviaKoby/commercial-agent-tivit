from __future__ import annotations


class SchemaValidator:
    def find_missing_columns(
        self, actual_columns: list[str], required_columns: list[str]
    ) -> list[str]:
        actual = {column.strip() for column in actual_columns}
        return [column for column in required_columns if column not in actual]
