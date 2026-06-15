FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

RUN useradd --create-home appuser

COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-dev

COPY src ./src

USER appuser

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "sales_assistant.main:app", "--host", "0.0.0.0", "--port", "8080"]
