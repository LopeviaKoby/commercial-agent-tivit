from sales_assistant.validation.schema_validator import SchemaValidator


def test_schema_validator_reports_missing_columns() -> None:
    validator = SchemaValidator()

    result = validator.find_missing_columns(
        actual_columns=["country", "acv"],
        required_columns=["country", "acv", "phase"],
    )

    assert result == ["phase"]
