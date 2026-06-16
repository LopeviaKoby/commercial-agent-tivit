from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from pathlib import Path as SysPath

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_env: str = "local"
    log_level: str = "INFO"
    data_input_dir: str = "data/input"
    data_output_dir: str = "data/output"
    persistence_mode: str = "local"
    bigquery_dataset: str = ""
    bigquery_location: str = ""
    salesforce_org_alias: str = "tivit-prod-api"
    salesforce_cli_timeout_seconds: int = 60
    salesforce_query_limit: int | None = None
    salesforce_max_records: int = 10000
    salesforce_raw_dir: str = "salesforce_poc/raw"
    salesforce_curated_dir: str = "salesforce_poc/curated"
    salesforce_live_fallback_enabled: bool = True
    google_cloud_project: str = "planillas-acv-tivit"
    google_cloud_location: str = "us-central1"
    google_genai_use_vertexai: bool = True
    vertex_model_fast: str = "gemini-2.5-flash"
    vertex_model_reasoning: str = ""
    llm_timeout_seconds: int = 30
    port: int = 8080

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


def resolve_optional_project_path(path: str | SysPath | None) -> Path | None:
    if path is None:
        return None
    return resolve_project_path(path)
