"""FastAPI application for Quarry."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter
from prometheus_fastapi_instrumentator import Instrumentator

from api.routes.search import router as search_router
from config.logging import configure_logging
from pipeline.cache import close_redis, get_redis
from pipeline.http import (
    close_http_client,
    create_http_client,
)
from pipeline.resilience import ShutdownManager

configure_logging()

shutdown_manager = ShutdownManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # -------------------------
    # Startup
    # -------------------------

    await create_http_client()

    redis = get_redis()
    await FastAPILimiter.init(redis)

    shutdown_manager.register_cleanup(close_http_client)
    shutdown_manager.register_cleanup(close_redis)

    try:
        yield

    finally:
        # -------------------------
        # Shutdown
        # -------------------------
        await shutdown_manager.shutdown()


app = FastAPI(
    title="Quarry",
    summary="Deterministic web retrieval, extraction, cleaning, and compression.",
    description=(
        "Quarry searches SearXNG, optionally crawls and ranks web pages, then "
        "returns cleaned Markdown documents. Open the **Search** endpoint for "
        "field-by-field behavior and a ready-to-run example."
    ),
    version="0.7.0",
    openapi_tags=[
        {
            "name": "Search",
            "description": "Retrieve, optionally crawl/rank, clean, and optionally compress web documents.",
        },
        {
            "name": "System",
            "description": "Service metadata and liveness checks.",
        },
    ],
    lifespan=lifespan,
)
# Initialize and instrument the FastAPI application
Instrumentator().instrument(app).expose(app)


@app.get("/", tags=["System"], summary="Get service metadata")
async def root() -> dict[str, str]:
    """Return basic service metadata."""

    return {"service": "Quarry"}


@app.get("/health", tags=["System"], summary="Check API liveness")
async def health() -> dict[str, str]:
    """Return a lightweight health response."""

    return {"status": "ok"}


app.include_router(search_router)
