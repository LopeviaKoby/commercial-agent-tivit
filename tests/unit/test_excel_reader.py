from pathlib import Path

from sales_assistant.ingestion.excel_reader import ExcelReader


def test_excel_reader_lists_supported_files(tmp_path: Path) -> None:
    (tmp_path / "pipeline.xlsx").write_text("", encoding="utf-8")
    (tmp_path / "budget.csv").write_text("", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("", encoding="utf-8")

    reader = ExcelReader()

    result = reader.list_supported_files(tmp_path)

    assert [path.name for path in result] == ["budget.csv", "pipeline.xlsx"]
