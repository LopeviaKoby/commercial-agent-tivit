from __future__ import annotations

from sales_assistant.persistence.repository import CuratedDataset


class BigQueryRepository:
    def load_dataset(self) -> CuratedDataset:
        raise NotImplementedError("BigQuery sigue siendo opcional en este PoC.")

    def healthcheck(self) -> bool:
        return False
