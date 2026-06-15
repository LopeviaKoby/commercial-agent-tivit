from __future__ import annotations

from typing import Protocol


class Repository(Protocol):
    def load_dataset(self) -> object: ...

    def get_metric_source(self, metric_id: str) -> object: ...

    def healthcheck(self) -> bool: ...
