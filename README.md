![CI](https://github.com/RHarish1/quarry/actions/workflows/ci.yml/badge.svg)
![Docker](https://github.com/RHarish1/quarry/actions/workflows/docker.yml/badge.svg)
![CodeQL](https://github.com/RHarish1/quarry/actions/workflows/codeql.yml/badge.svg)

# Quarry

Quarry is an LLM-native retrieval backend. It searches SearXNG, optionally
crawls and ranks candidate pages, then returns cleaned and optionally compressed
Markdown through a REST API.

## Architecture

```mermaid
flowchart TD
  Client([Client]) --> API[POST /search]
  API --> Limit{Within 30 requests/minute?}
  Limit -->|No| Throttle[429 response]
  Limit -->|Yes| Normalize[Optional query normalization]
  Normalize --> Cache{Caching enabled and hit?}
  Cache -->|Yes| Cached[Return cached SearchResponse]
  Cache -->|No| Retrieve[SearXNG retrieval]
  Retrieve --> Crawl{crawl_websites?}
  Crawl -->|No| Snippets[Use SearXNG snippets]
  Crawl -->|Yes| Rank{Deterministic ranking?}
  Rank -->|No| All[Fetch and extract all candidates]
  Rank -->|Yes| Robots[Check robots.txt]
  Robots --> Filter[Filter candidates]
  Filter --> Batch[Crawl next candidate batch]
  Batch --> Target{Enough qualified documents?}
  Target -->|No, candidates remain| Batch
  Target -->|Yes or exhausted| Selected[Sort and select documents]
  Snippets --> Clean[Deterministic cleaning]
  All --> Clean
  Selected --> Clean
  Clean --> Compress{compress_output?}
  Compress -->|Yes| Reduce[Token-budgeted compression]
  Compress -->|No| Store{Cache response?}
  Reduce --> Store
  Store --> Response([SearchResponse + timings])
  Store -->|Yes| Redis[(Redis)]
```

## Quick Start

Start the complete development stack, including SearXNG and Redis:

```bash
docker compose up --build
```

The API is available at `http://localhost:8000`; its health endpoint is
`GET /health`. SearXNG is exposed at `http://localhost:8080`, and Redis at
`localhost:6379`.

Use `docker compose`, not the API image alone, for a plug-and-play start. The
Dockerfile builds only the API container; Compose provides the required SearXNG
and Redis services.

## Local Development

Quarry requires reachable SearXNG and Redis instances. Install the project with
your preferred Python package manager, then run the application with connection
settings appropriate for services running on your host:

```bash
uv sync
SEARXNG_BASE_URL=http://localhost:8080 \
REDIS_URL=redis://localhost:6379/0 \
uv run uvicorn api.app:app --reload
```

The application does not load a `.env` file automatically. Export variables in
your shell, configure them in your process manager, or pass an environment file
to the command that starts the app.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SEARXNG_BASE_URL` | `http://localhost:8080` | URL of the SearXNG service. |
| `SEARXNG_TIMEOUT_SECONDS` | `20` | Timeout for SearXNG requests. |
| `CRAWL_TIMEOUT_SECONDS` | `15` | Timeout for crawling a page. |
| `CRAWL_MAX_CONCURRENCY` | `5` | Maximum number of concurrent crawls. |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL used for response caching. |

The defaults use Docker Compose service names. Override `SEARXNG_BASE_URL` and
`REDIS_URL` when running the API outside that Compose network.

Redis is initialized during API startup for rate limiting and is also used for
optional response caching. Cached search responses expire after one hour.

`APP_ENV`, although set by `docker-compose.yml`, is not read by the application.
It is therefore not a Quarry configuration variable.

`POST /search` returns:

- `request_id`
- `query`
- `timings`
- `documents`

Each document is a `CleanDocument` that preserves the raw document fields and adds deterministic cleaning metrics.

`SearchResponse.timings` reports search, crawl, cleaning, optional compression,
and total pipeline latency in milliseconds.

Each API process assigns one UUID request identifier at startup. It is returned
as `request_id` on responses from that process.

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
- `GET /health` reports whether the API process is running.

See [the Search API reference](docs/search-api.md) for request fields and an
example.

## Request Flow

For the complete lifecycle of a request—including rate limiting, caching,
retrieval, extraction fallbacks, cleaning, and failure behavior—see the
[request-flow guide](docs/request-flow.md).

## Stage Documentation

The processing pipeline is documented stage by stage:

- [Retrieval](docs/retrieval.md): SearXNG request construction and result normalization.
- [Crawling](docs/crawling.md): page fetching, HTML-to-Markdown conversion, and fallbacks.
- [Cleaning](docs/cleaning.md): deterministic Markdown transformations and metrics.
- [Compression](docs/compression.md): optional token-budgeted output reduction.
- [Caching](docs/caching.md): Redis lifecycle, key construction, and expiration.
- [Resilience and observability](docs/resilience-observability.md): shared HTTP
  lifecycle, retries, circuit breakers, graceful shutdown, and internal metrics.

## Project Layout

- `config/`: application configuration and provider definitions
- `api/`: FastAPI app, routes, schemas, and middleware
- `pipeline/`: retrieval pipeline packages
- `models/`: shared data models
- `utils/`: shared utilities
- `tests/`: unit, integration, and dataset-based test resources
- `scripts/`: helper scripts, including benchmark tooling
- `docs/`: project documentation
