from __future__ import annotations

from fastapi import FastAPI

from sales_assistant import __version__
from sales_assistant.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Commercial Sales Assistant",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(router)
    return app


app = create_app()
