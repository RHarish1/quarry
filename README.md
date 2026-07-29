# Quarry

Quarry is an LLM-native retrieval backend. It accepts a search query, retrieves candidate URLs via SearXNG, fetches and parses the matching pages over HTTP, deterministically cleans the markdown, and returns structured results through a REST API.

## Architecture

```mermaid
flowchart LR
  Client[Client] --> API[FastAPI API]
  API --> Pipeline[Retrieval Pipeline]
   Pipeline --> Search[SearXNG Search]
   Pipeline --> Crawler[Crawl4AI Crawler]
   Pipeline --> Cleaner[Deterministic Cleaner]
   Search --> URLs[Candidate URLs]
   Crawler --> Document[Document]
   Cleaner --> CleanDocument[CleanDocument]
   API --> Response[SearchResponse]
```

## Quick Start

1. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the API:

   ```bash
   uvicorn api.app:app --reload
   ```

## Docker

Bring up the full stack with SearXNG and Redis:

```bash
docker compose up --build
```

Use `docker compose`, not the API image alone, for a plug-and-play start. The Dockerfile builds only the API container; the compose file provides the required SearXNG and Redis services.

The API reads `SEARXNG_BASE_URL` from the environment and normalizes the upstream JSON response into `SearchResponse`.

`POST /search` returns:

- `query`
- `timings`
- `documents`

Each document is a `CleanDocument` that preserves the raw document fields and adds deterministic cleaning metrics.

## Development Setup

- Python 3.12+
- FastAPI
- Uvicorn
- Pydantic v2
- Ruff
- Black
- Pytest
- httpx
- BeautifulSoup4

## API

- `POST /search` accepts a `SearchRequest` body, calls SearXNG over HTTP, crawls the returned URLs, cleans the markdown, and returns a normalized `SearchResponse`.

## Project Layout

- `config/`: application configuration and provider definitions
- `api/`: FastAPI app, routes, schemas, and middleware
- `pipeline/`: retrieval pipeline packages
- `models/`: shared data models
- `utils/`: shared utilities
- `benchmarks/`: benchmark scaffolding
- `tests/`: test scaffolding
- `scripts/`: helper scripts
- `docs/`: project documentation
