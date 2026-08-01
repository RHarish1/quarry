"""FastAPI application for Quarry."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter

from api.routes.search import router as search_router
from config.logging import configure_logging
from pipeline.cache import close_redis, get_redis

configure_logging()


@asynccontextmanager
async def lifespan(app):
    redis = get_redis()
    await FastAPILimiter.init(redis)
    yield
    await close_redis()


app = FastAPI(title="Quarry", lifespan=lifespan)


@app.get("/")
async def root() -> dict[str, str]:
    """Return basic service metadata."""

    return {"service": "Quarry"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a lightweight health response."""

    return {"status": "ok"}


app.include_router(search_router)
