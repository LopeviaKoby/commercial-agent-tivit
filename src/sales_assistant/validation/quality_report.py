from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class QualityReportBuilder:
    warnings: list[str] = field(default_factory=list)

    def add_warning(self, warning: str) -> None:
        self.warnings.append(warning)
