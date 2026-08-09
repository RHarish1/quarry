# Resilience and Observability

Quarry shares a **single asynchronous HTTPX client** across SearXNG retrieval,
robots.txt checks, and page fetching. The client is created during FastAPI
startup via `pipeline/http/client.py` and closed during graceful shutdown.

```
User-Agent : QuarryBot/0.6
Timeout    : 30 s (httpx.Timeout)
Max conns  : 100
Keep-alive : 20
Redirects  : followed
```

This single pool is shared by all inbound requests concurrently. No new TCP
connection is established per-request — the OS-level socket is reused across
the keep-alive pool.

## Retry Policies (`pipeline/resilience/policies.py`)

Retries use exponential backoff with random jitter. They apply only to
configured transient exception types (`TimeoutError`, `asyncio.TimeoutError`,
`ConnectionError`) and retryable HTTP status codes (408, 429, 500, 502, 503, 504).
Non-transient failures are raised immediately without retrying.

The backoff formula is:

```
delay = min(base_delay × (backoff_multiplier ^ attempt), max_delay) + uniform(0, jitter)
```

| Policy | Max retries | Base delay | Max delay | Jitter |
| --- | ---: | ---: | ---: | ---: |
| `SEARCH_PROVIDER_RETRY` | 3 | 250 ms | 2 s | ±200 ms |
| `CRAWLER_RETRY` | 2 | 500 ms | 4 s | ±300 ms |
| `REDIS_RETRY` | 2 | 100 ms | 1 s | ±50 ms |
| `DEFAULT_RETRY` | 3 | 500 ms | 8 s | ±250 ms |
| `NO_RETRY` | 0 | — | — | — |

## Circuit Breakers (`pipeline/resilience/policies.py`)

Each dependency has a `CircuitBreaker` instance. A breaker tracks consecutive
failures and moves through three states:

```
CLOSED ──(failures ≥ threshold)──► OPEN ──(timeout elapsed)──► HALF_OPEN
   ▲                                                                  │
   └──────────────(probe succeeds)──────────────────────────────────-┘
   (probe fails → back to OPEN)
```

Only **one** half-open probe is permitted at a time (guarded by `asyncio.Lock`).

| Breaker | Failure threshold | Recovery timeout |
| --- | ---: | ---: |
| `FAST_PROVIDER_BREAKER` (SearXNG, Brave, DDG) | 5 | 20 s |
| `SLOW_PROVIDER_BREAKER` (Playwright) | 3 | 60 s |
| `CRAWLER_BREAKER` | 4 | 30 s |
| `REDIS_BREAKER` | 5 | 15 s |

A `CircuitOpenError` is raised instantly when the breaker is OPEN, preventing
repeated downstream calls during an outage.

## Graceful Shutdown (`pipeline/resilience/shutdown.py`)

`ShutdownManager` is registered in the FastAPI lifespan. On shutdown signal:

1. **Cancel tasks** — all registered `asyncio.Task` objects are cancelled and awaited with `return_exceptions=True`.
2. **Run cleanup callbacks** — registered callbacks are run in **reverse** registration order (LIFO), so the HTTPX client and Redis client close after their dependents.
3. **Idempotent** — a `asyncio.Lock` + boolean flag prevent double-shutdown.

Registration order in `api/app.py`:

```python
shutdown_manager.register_cleanup(close_http_client)  # closes first on shutdown (last registered)
shutdown_manager.register_cleanup(close_redis)         # closes second (registered first, runs last)
```

Wait — callbacks run in **reverse**, so `close_redis` runs before `close_http_client`.

## Prometheus Metrics (`api/metrics.py`)

Custom application metrics are defined using `prometheus_client` and emitted
from the `POST /search` route after each pipeline execution.

| Metric name | Type | Description |
| --- | --- | --- |
| `quarry_search_cache_hits_total` | Counter | Requests served from Redis cache |
| `quarry_cache_lookup_ms` | Histogram | Time spent reading the cache (ms) |
| `quarry_urls_found_total` | Counter | Candidate URLs returned by all providers |
| `quarry_pages_crawled_total` | Counter | Pages successfully fetched and extracted |
| `quarry_crawl_failures_total` | Counter | Pages that failed fetch or extraction |
| `quarry_compression_ratio` | Histogram | Byte-level compression ratio distribution |
| `quarry_tokens_saved_total` | Counter | Tokens removed by the compression stage |

FastAPI HTTP metrics (request duration, status codes, in-flight count) are
additionally exposed by `prometheus-fastapi-instrumentator` at `GET /metrics`.

Prometheus scrapes `api:8000/metrics` every **10 seconds** (configured in
`prometheus.yml`). Grafana is pre-wired to Prometheus as a datasource.

## Internal Benchmark Object (`SearchBenchmark`)

Each pipeline execution creates a `SearchBenchmark` populated with:

| Field | Description |
| --- | --- |
| `cache_hit` | Whether the response came from Redis |
| `cache_lookup_ms` | Time spent on the cache read |
| `cache_write_ms` | Time spent writing the response to cache |
| `urls_found` | Total candidate URLs before dedup |
| `crawlable_urls` | URLs allowed after robots.txt (ranked mode) |
| `urls_filtered_out` | URLs removed by candidate filtering |
| `pages_successfully_crawled` | Documents accepted |
| `crawl_failures` | Documents that failed or were rejected |
| `bytes_before` / `bytes_after` | Raw document bytes before/after cleaning+compression |
| `tokens_before` / `tokens_after` | Estimated token counts before/after |
| `compression_ratio` *(property)* | `bytes_after / bytes_before` |
| `token_reduction_ratio` *(property)* | `(before - after) / before` |

The `benchmark` object is included in every `SearchResponse` and also drives
the Prometheus metric emissions in the route handler.
