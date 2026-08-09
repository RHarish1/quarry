# Testing Guide

Quarry uses **pytest** for all tests, managed via `uv`. Tests are separated into
three suites: unit, integration, and dataset files for the benchmark runner.

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific suite
uv run pytest tests/unit/
uv run pytest tests/integration/

# Run with coverage report
uv run pytest --cov=api --cov=pipeline --cov=models --cov-report=term-missing

# Run a specific test file
uv run pytest tests/unit/test_crawler.py -v
```

## Test Structure

```
tests/
├── unit/
│   ├── test_cleaner.py          # Cleaning level transformations
│   ├── test_compressor.py       # Token-budget paragraph compression
│   ├── test_crawler.py          # Extraction waterfall, quality scoring, fallback docs
│   ├── test_openapi_docs.py     # OpenAPI schema generation (route registration)
│   ├── test_ranking_flow.py     # Queue-based ranked crawl orchestration
│   ├── test_searxng.py          # SearXNG result normalisation
│   └── test_tokens.py           # Token count estimator
├── integration/
│   └── test_search_api.py       # Full FastAPI route with monkeypatched pipeline
└── datasets/
    ├── easy_queries.txt
    ├── medium_queries.txt
    └── hard_queries.txt          # Used by scripts/benchmark.py
```

## Unit Tests

### `test_crawler.py`

Covers the extraction waterfall, `ExtractorManager`, quality scoring, and the
crawler's fallback behaviour:

- `test_quality_accepts_article_like_content` — verifies `score_extraction()`
  accepts well-formed article HTML with customised thresholds.
- `test_extractor_manager_falls_back_to_later_extractor` — uses `FakeExtractor`
  stubs to confirm the manager returns the highest-quality result when the
  primary extractor scores below threshold.
- `test_crawler_preserves_internal_html_only` — monkeypatches `fetch_raw_document`
  and `ExtractorManager` to confirm:
  - `Document.html` is always `None` in output (raw HTML never leaks to API)
  - Failed fetches produce a fallback doc with `crawl_status: "fetch_failed"`
  - Successful docs carry `extraction_method` in metadata and correct `crawl_status`

### `test_cleaner.py`

Tests deterministic cleaning transformations at each level (0–3). Validates
that `CleanDocument` records correct `cleaning_steps_applied`, token counts,
and reduction percentages.

### `test_compressor.py`

Tests paragraph splitting, duplicate removal, boilerplate detection, and the
token budget cutoff. Verifies `deterministic_compression` appears in
`cleaning_steps_applied` and that `cleaned_token_count ≤ target_token_budget`.

### `test_ranking_flow.py`

Tests the queue-based `crawl_and_rank_documents` orchestrator: worker
cancellation on target, quality filtering at `MIN_QUALITY_SCORE`, and
benchmark field population.

### `test_searxng.py`

Tests SearXNG result parsing: valid results, malformed items, missing `results`
key, non-list `results` field.

### `test_tokens.py`

Tests the lightweight regex-based token estimator used throughout cleaning and
compression.

### `test_openapi_docs.py`

Confirms the FastAPI app generates a valid OpenAPI schema and that key routes
(`/search`, `/health`, `/metrics`) are registered.

## Integration Tests

### `test_search_api.py`

Exercises the full `POST /search` route using FastAPI's `TestClient`. The
pipeline is monkeypatched so no real network calls are made:

```python
monkeypatch.setattr(pipeline_module, "search_searxng", fake_search_searxng)
monkeypatch.setattr(pipeline_module, "crawl_documents", fake_crawl_documents)
monkeypatch.setattr(pipeline_module, "clean_documents", fake_clean_documents)
app.dependency_overrides[DEFAULT_RATE_LIMIT.dependency] = lambda: None
```

Asserts:
- HTTP 200
- `query` field in response
- `documents[0].url` matches the fake result
- `documents[0].cleaned_markdown` is populated
- `timings` present with `compression_latency_ms == 0.0` (compression disabled)
- `timings.total_request_latency_ms >= 0`

## CI Configuration

The `ci.yml` workflow runs on every push/PR to `main`:

```yaml
services:
  redis:  redis:7-alpine   (port 6379)
  searxng: searxng/searxng (port 8080)

steps:
  uv sync --locked --extra dev
  uv run ruff check .
  uv run black --check .
  uv run pytest
```

Tests run with live Redis and SearXNG services in GitHub Actions, matching the
Docker Compose environment as closely as possible.

## Linting and Formatting

```bash
# Lint
uv run ruff check .

# Format check
uv run black --check .

# Auto-fix formatting
uv run black .
```

`pyproject.toml` configuration:

```toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.black]
line-length = 88
target-version = ["py312"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
pythonpath = ["."]
```
