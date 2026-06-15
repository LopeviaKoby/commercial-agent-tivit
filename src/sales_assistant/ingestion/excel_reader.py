from __future__ import annotations

from pathlib import Path

from sales_assistant.ingestion.workbook_loader import SUPPORTED_EXTENSIONS, load_tabular_sheet


class ExcelReader:
    supported_extensions = SUPPORTED_EXTENSIONS

    def list_supported_files(self, input_dir: Path) -> list[Path]:
        if not input_dir.exists():
            return []

        return sorted(
            path
            for path in input_dir.iterdir()
            if path.is_file() and path.suffix.lower() in self.supported_extensions
        )

    def load_tabular_sheet(
        self,
        path: Path,
        sheet_name: str | None = None,
        header_row: int | None = None,
    ):
        return load_tabular_sheet(path, sheet_name=sheet_name, header_row=header_row)
