# Commercial Sales Assistant Prototype

## Proposito

Este repositorio contiene la base de la Fase 1 de un prototipo para consultar datos comerciales almacenados en archivos Excel y CSV sin acoplar la logica deterministica con la capa de IA.

## Alcance actual

- Estructura minima del proyecto.
- Configuracion base de Python 3.12 con `uv`.
- Aplicacion FastAPI minima con `GET /health`.
- Capas de ingesta, validacion, negocio, LLM, orquestacion y persistencia.
- Pruebas smoke para verificar imports y salud de la API.

## Arquitectura

1. Ingestion: lectura de archivos locales.
2. Validation: normalizacion y reportes de calidad.
3. Business: perfilado y reglas deterministicas de exploracion.
4. LLM: interpretacion de intencion y redaccion final.
5. Orchestration: reservado para flujos posteriores del producto.
6. Persistence: modo local y modo BigQuery opcional.

## Instalacion

```powershell
uv python install 3.12
uv sync
```

## Ejecucion local

```powershell
uv run uvicorn sales_assistant.main:app --reload
```

## Pruebas y calidad

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Datos de entrada

- Coloca los archivos fuente en `data/input`.
- No agregues archivos comerciales reales al repositorio.
- Si no existen archivos aun, conserva la estructura y utiliza `data/input/.gitkeep`.

## Estado

Documentacion principal:

- [docs/current_state.md](docs/current_state.md)
- [docs/pending_validations.md](docs/pending_validations.md)
- [docs/data_dictionary.yaml](docs/data_dictionary.yaml)
- [docs/business_rules.yaml](docs/business_rules.yaml)
- [docs/metric_catalog.yaml](docs/metric_catalog.yaml)
