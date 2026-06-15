# Repository Guidelines

## Setup

- Use PowerShell 7 (`pwsh`) for every terminal command.
- Install Python 3.12 with `uv python install 3.12`.
- Sync dependencies with `uv sync`.

## Quality

- Run lint with `uv run ruff check .`.
- Run format check with `uv run ruff format --check .`.
- Run tests with `uv run pytest`.

## Conventions

- Keep technical identifiers in English and functional documentation in Spanish.
- Separate ingestion, validation, business logic, LLM, orchestration, and persistence concerns.
- Do not couple deterministic business logic with the LLM layer.
- Do not invent business rules or column meanings; record unknowns as pending validation.
- Never overwrite source spreadsheets or expose sensitive data in code, logs, or committed artifacts.
- Los analisis puntuales deben realizarse directamente sobre los datos y resumirse
  en la salida del chat o en el documento canonico vigente.
- No crear scripts ni documentos permanentes para tareas de una sola ejecucion.
- Si se crea un script auxiliar temporal para inspeccion o diagnostico, debe
  eliminarse al finalizar la tarea, despues de conservar unicamente la logica
  reutilizable y los resultados necesarios.
- Solo conservar un artefacto cuando:
  - forme parte del flujo recurrente;
  - sea consumido por codigo;
  - sea una fuente canonica;
  - o sea necesario para reproducibilidad tecnica.
