"""FastAPI application for Quarry."""

from fastapi import FastAPI

app = FastAPI(title="Quarry")


@app.get("/")
async def root() -> dict[str, str]:
    """Return basic service metadata."""

    return {"service": "Quarry"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a lightweight health response."""

    return {"status": "ok"}
