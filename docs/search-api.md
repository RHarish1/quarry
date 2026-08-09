# Search API

`POST /search` is the primary endpoint. It runs the retrieval → crawl → clean
→ compress pipeline and returns a `SearchResponse`.

Rate limit: **30 requests per 60 seconds** (Redis-backed, per client). Requests
with header `x-benchmark: true` bypass the limiter.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/search` | Search, optionally crawl, clean, and compress |
| `GET` | `/health` | Liveness check → `{"status":"ok"}` |
| `GET` | `/` | Service metadata → `{"service":"Quarry"}` |
| `GET` | `/metrics` | Prometheus metrics (auto-exposed by instrumentator) |

## Request Body (`SearchRequest`)

`query` is the only required field. All others are optional.

```json
{
  "query": "FastAPI lifespan",
  "format": "default",
  "cleaning_level": 2,
  "crawl_websites": true,
  "rank_and_score_deterministically": true,
  "target_documents": 5,
  "enable_caching": true,
  "compress_output": true,
  "target_token_budget": 2048,
  "enhance_query": true,
  "language": "en",
  "time_range": "week",
  "engines": ["google"],
  "categories": ["general"]
}
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `query` | `str` | **required** | Search query (min length 1) |
| `format` | `default\|text_only\|content_only\|url_only` | `default` | Controls which payload field is populated |
| `cleaning_level` | `0\|1\|2\|3` | `0` | Cleaning intensity (see [Cleaning](cleaning.md)) |
| `crawl_websites` | `bool` | `false` | Fetch and extract pages |
| `rank_and_score_deterministically` | `bool` | `false` | Queue-based ranked crawl (requires `crawl_websites=true`) |
| `target_documents` | `int ≥ 1` | `10` | Stop ranked crawl after N quality docs; also governs retrieval fallback thresholds |
| `enable_caching` | `bool` | `false` | Read/write Redis cache |
| `compress_output` | `bool` | `false` | Paragraph-level compression after cleaning |
| `target_token_budget` | `int ≥ 1 \| null` | `null` | Per-document token limit (default 2048); 4 chars ≈ 1 token |
| `enhance_query` | `bool` | `false` | Deterministic query normalisation before retrieval |
| `time_range` | `day\|week\|month\|year\|null` | `null` | SearXNG recency filter |
| `language` | `str \| null` | `null` | SearXNG language code |
| `engines` | `list[str]` | `[]` | SearXNG engine names (order doesn't affect cache key) |
| `categories` | `list[str]` | `[]` | SearXNG category names (order doesn't affect cache key) |

## Example Request

```bash
curl -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "FastAPI lifespan",
    "crawl_websites": true,
    "cleaning_level": 1,
    "compress_output": true,
    "target_token_budget": 2048
  }'
```

## Response Body (`SearchResponse`)

```jsonc
{
  "success": true,
  "request_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",  // uuid4() per request
  "query": "fastapi lifespan",                             // normalised query
  "timings": {
    "search_latency_ms": 312.4,
    "crawl_latency_ms": 4102.1,
    "cleaning_latency_ms": 18.2,
    "compression_latency_ms": 5.6,
    "total_request_latency_ms": 4441.8
  },
  "benchmark": {
    "timings": { /* same as above */ },
    "cache_hit": false,
    "cache_lookup_ms": 1.2,
    "cache_write_ms": 3.1,
    "urls_found": 12,
    "crawlable_urls": 10,
    "urls_filtered_out": 2,
    "pages_successfully_crawled": 5,
    "crawl_failures": 1,
    "average_crawl_depth": 0.0,
    "bytes_before": 142000,
    "bytes_after": 18400,
    "tokens_before": 35500,
    "tokens_after": 4600
  },
  // Only ONE of the three payload fields is present (others are omitted):
  "documents": [ /* list[CleanDocument] — format=default */ ],
  "formatted_content": "...",  /* str — format=text_only | content_only */
  "urls": ["..."]              /* list[str] — format=url_only */
}
```

`None` fields are stripped automatically (`response_model_exclude_none=True`).

### `CleanDocument` fields

Each document in the `documents` list:

| Field | Description |
| --- | --- |
| `id` | UUID hex |
| `url` | Final URL after redirects |
| `canonical_url` | Source URL |
| `title` | Page title |
| `markdown` | Raw extracted markdown |
| `html` | Always `null` in API responses |
| `crawl_status` | `skipped`, `trafilatura`, `playwright_trafilatura`, `readability`, `fetch_failed`, `extract_failed` |
| `crawl_latency_ms` | Fetch + extraction time |
| `content_type` | HTTP content type |
| `metadata` | Provider fields + quality score + extraction method |
| `cleaned_markdown` | Markdown after cleaning (+ compression if enabled) |
| `original_token_count` | Tokens before cleaning |
| `cleaned_token_count` | Tokens after cleaning/compression |
| `tokens_removed` | `original - cleaned` |
| `reduction_percentage` | `tokens_removed / original × 100` |
| `cleaning_latency_ms` | Time spent cleaning this document |
| `cleaning_steps_applied` | Ordered list of step names that ran |

### `timings` fields

| Field | Description |
| --- | --- |
| `search_latency_ms` | Retrieval chain (all providers) |
| `crawl_latency_ms` | Crawl stage including ranking when enabled |
| `cleaning_latency_ms` | Cleaning stage |
| `compression_latency_ms` | Compression stage (`0.0` if disabled or skipped) |
| `total_request_latency_ms` | Wall-clock from retrieval start to compression end |

## Error Responses

| HTTP status | Cause |
| --- | --- |
| `200` (with `success: false`) | Pipeline stage failed; empty payload, partial timings |
| `422` | Request body does not match `SearchRequest` |
| `429` | Rate limit exceeded (30 req / 60 s) |

For the complete lifecycle and failure behaviour, see [Request Flow](request-flow.md).
