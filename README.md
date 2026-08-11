![CI](https://github.com/RHarish1/quarry/actions/workflows/ci.yml/badge.svg)
![Docker](https://github.com/RHarish1/quarry/actions/workflows/docker.yml/badge.svg)
![CodeQL](https://github.com/RHarish1/quarry/actions/workflows/codeql.yml/badge.svg)
![Benchmark](https://github.com/RHarish1/quarry/actions/workflows/benchmark.yml/badge.svg)

# Quarry

Quarry is an LLM-native retrieval backend. It searches a resilient multi-provider chain (Tavily → SearXNG → Brave → DuckDuckGo), optionally crawls and ranks candidate pages through a 3-stage extraction waterfall, then returns cleaned and optionally compressed Markdown through a REST API.

## Motivation

Large Language Models (LLMs) require high-quality, noise-free context to produce accurate outputs and avoid hallucinations. Traditional web search APIs are optimized for humans, they return links and short snippets, not structured knowledge.

As a result, developers are forced to:
- Build custom scrapers  
- Strip HTML boilerplate  
- Handle anti-bot mechanisms  
- Fit content into strict token limits  

This adds unnecessary complexity and inefficiency.

**Quarry solves this problem.**

It acts as a deterministic retrieval layer that:
- Fetches web content  
- Cleans and normalizes HTML  
- Deduplicates redundant data  
- Compresses content into high-density Markdown  

This ensures that LLMs spend their context window on **actual information**, not noise like ads or navigation menus.

**Outcome:**
- Fewer tokens used  
- Lower latency and bandwidth  
- Standardized, reliable retrieval  
- Resilient fallback across multiple search providers  

## System Architecture

```mermaid
flowchart TD
  subgraph DockerNetwork["Docker Compose Network"]
    subgraph API["Quarry API Container (port 8000)"]
      AppStartup["FastAPI Lifespan\n─────────────\nCreate shared HTTPX client\nInit Redis rate limiter\nRegister shutdown hooks"]
      Route["POST /search\n─────────────\nPydantic validation\nRate limit (30 req/60s)\nGenerate request_id (UUID)"]
      Pipeline["Pipeline Orchestrator\npipeline/pipeline.py"]
      QueryNorm["Query Normalizer\n(enhance_query=true)\nUnicode · quotes · case\npunctuation · whitespace · tokens"]
      CacheRead["Redis Cache Read\nsearch:<sha256> key"]
      
      subgraph Retrieval["Retrieval Chain (fallback)"]
        T["1. Tavily\n(primary)"]
        S["2. SearXNG\n(if Tavily < target*2)"]
        B["3. Brave Search\n(if total < target)"]
        D["4. DuckDuckGo\n(if still < target)"]
      end

      Dedup["Deduplicate URLs\n(preserve insertion order)"]

      subgraph Crawl["Crawl Stage (crawl_websites=true)"]
        Robots["robots.txt check\n(ranked mode only)"]
        Filter["Candidate Filtering\nblock-list · dupes · extensions\nlogin/privacy/terms paths"]
        
        subgraph RankedCrawl["Ranked Crawl (rank_and_score_deterministically=true)"]
          Queue["asyncio.Queue\n(task + result queues)"]
          Workers["N concurrent workers\n(N = CRAWL_MAX_CONCURRENCY)"]
          QualityFilter["Quality Filter\nscore ≥ MIN_QUALITY_SCORE\nStop when target_documents reached"]
        end

        subgraph ExtractWaterfall["Extraction Waterfall (per URL)"]
          E1["1. Trafilatura\n(raw HTML)"]
          E2["2. Playwright + Trafilatura\n(JS-rendered HTML)"]
          E3["3. readability-lxml + Markdownify\n(final fallback)"]
          QScore["Deterministic Quality Score\nchars · words · paragraphs\ncontent/HTML ratio · link density\nnavigation ratio · title"]
        end
      end

      SnippetPath["Snippet Path\n(crawl_websites=false)\ncrawl_status: skipped"]

      subgraph Cleaning["Cleaning Stage"]
        L0["Level 0: normalize whitespace"]
        L1["Level 1: + cookie/consent\n+ duplicate paragraphs"]
        L2["Level 2: + nav/footer/ads\n+ duplicate headings"]
        L3["Level 3: + empty sections"]
      end

      subgraph Compression["Compression Stage (compress_output=true)"]
        Split["Split into paragraphs"]
        DedupPara["Remove duplicate &\nboilerplate paragraphs"]
        Budget["Keep paragraphs until\ntoken budget reached\n(regex tokenizer)"]
      end

      FormatOut["Output Formatter\ndefault · text_only\ncontent_only · url_only"]
      CacheWrite["Redis Cache Write\nTTL: 3600s\n(non-empty responses only)"]
      Metrics["Prometheus Metrics\n/metrics endpoint\nquarry_* counters + histograms"]
      Response["SearchResponse\nrequest_id · query · timings\nbenchmark · documents/content/urls"]
    end

    Redis[("Redis\nport 6379\n────────\nRate limiting\nResponse cache")]
    SearXNG["SearXNG\nport 8080 (internal)\n────────\nJSON search API"]
    Prometheus["Prometheus\nport 9090\nscrape interval: 10s"]
    Grafana["Grafana\nport 3000\nquarry-api dashboard"]
  end

  Client(["HTTP Client"]) -->|"POST /search\nJSON body"| Route
  AppStartup -->|"single HTTPX client\n100 max conns / 20 keep-alive"| Retrieval
  AppStartup -->|"single HTTPX client"| ExtractWaterfall
  Route --> Pipeline
  Pipeline --> QueryNorm
  Pipeline --> CacheRead
  CacheRead -->|"cache hit"| Response
  CacheRead -->|"cache miss"| Retrieval
  T --> Dedup
  S --> Dedup
  B --> Dedup
  D --> Dedup
  Dedup --> Crawl
  Dedup --> SnippetPath
  Robots --> Filter
  Filter --> RankedCrawl
  Queue --> Workers
  Workers --> ExtractWaterfall
  E1 -->|"score ≥ threshold"| QScore
  E1 -->|"score < threshold"| E2
  E2 -->|"score ≥ threshold"| QScore
  E2 -->|"score < threshold"| E3
  E3 --> QScore
  QScore --> QualityFilter
  QualityFilter --> Cleaning
  SnippetPath --> Cleaning
  L0 --> L1 --> L2 --> L3
  Cleaning --> Compression
  Split --> DedupPara --> Budget
  Compression --> FormatOut
  FormatOut --> CacheWrite
  CacheWrite --> Redis
  CacheRead --- Redis
  FormatOut --> Metrics
  FormatOut --> Response
  Response -->|"JSON"| Client
  S -->|"POST /search form-encoded"| SearXNG
  AppStartup --- Redis
  Metrics -->|"scrape /metrics"| Prometheus
  Prometheus -->|"datasource"| Grafana
```

## Quick Start

Start the complete stack (API · SearXNG · Redis · Prometheus · Grafana):

```bash
docker compose up --build
```

| Service | URL | Notes |
| --- | --- | --- |
| Quarry API | `http://localhost:8000` | `GET /health` for liveness |
| SearXNG | `http://localhost:8080` | Internal to Compose network |
| Redis | `localhost:6379` | Rate limiter + response cache |
| Prometheus | `http://localhost:9090` | Scrapes `/metrics` every 10s |
| Grafana | `http://localhost:3000` | Login: `admin` / `quarry_admin` |

## Local Development (uv)

Quarry uses [`uv`](https://github.com/astral-sh/uv) for fast, lockfile-based dependency management.

```bash
# Install all dependencies from the lockfile
uv sync

# Run the API (requires running Redis and SearXNG)
SEARXNG_BASE_URL=http://localhost:8080 \
REDIS_URL=redis://localhost:6379/0 \
uv run uvicorn api.app:app --reload
```

The app does **not** call `load_dotenv`. Export variables in your shell, use a process manager, or pass `--env-file` to Docker.

Alternatively, you can run the development stack with hot-reload via Docker Compose:

```bash
docker compose -f docker-compose.dev.yml up --build
```

This mounts your local directory into the container, exposing internal debug ports and auto-reloading Uvicorn on code changes.

## Retrieval Chain

Quarry uses a sequential, multi-provider fallback strategy to maximise candidate coverage:

1. **Tavily** (primary) — called first on every request. Uses its own `httpx.AsyncClient` (10 s timeout) to POST to `https://api.tavily.com/search`. Returns empty results if `TAVILY_API_KEY` is unset.
2. **SearXNG** — called when Tavily returns fewer than `target_documents × 2` results. Uses the shared HTTPX client to GET `{SEARXNG_BASE_URL}/search?format=json`.
3. **Brave Search** — called when the combined total is still below `target_documents`. Uses its own `httpx.AsyncClient` (10 s timeout) with `X-Subscription-Token` header. Returns empty results if `BRAVE_API_KEY` is unset.
4. **DuckDuckGo** — ultimate free fallback when all others are insufficient. Uses the `ddgs` library with `backend="lite"`. Because DDGS is synchronous, the call is offloaded via `asyncio.to_thread()` to avoid blocking the event loop.

Results from all providers are concatenated and deduplicated by URL (first-seen wins).

## Single Shared HTTP Client

A single `httpx.AsyncClient` is created during FastAPI startup and shared across all outbound HTTP:

- SearXNG retrieval requests
- `robots.txt` fetches (ranked mode)
- Page crawl fetches

```
User-Agent : QuarryBot/0.6
Timeout    : 30 s
Max conns  : 100
Keep-alive : 20
```

This means the entire application maintains **one connection pool** — no TCP overhead per request, no race conditions on client lifecycle.

In benchmark mode (`x-mode: benchmark` header), the crawler switches to a Chrome user-agent to reduce bot-blocking from target sites.

## Pipeline Stages

| Stage | Module | Key behaviour |
| --- | --- | --- |
| Query normalisation | `pipeline/query/normalizer.py` | Unicode, quotes, case, punctuation, whitespace, duplicate tokens |
| Retrieval | `pipeline/retrieval/` | Tavily → SearXNG → Brave → DDG fallback chain |
| Crawling | `pipeline/crawler/` | Concurrent fetch with `asyncio.Semaphore`; extractor waterfall; fallback documents |
| Ranked crawling | `pipeline/ranking/manager.py` | `asyncio.Queue`-based streaming workers; stops when `target_documents` accepted |
| Extraction quality | `pipeline/crawler/quality.py` | Weighted score across 7 signals; `MIN_SCORE = 0.65` |
| Cleaning | `pipeline/cleaning/cleaner.py` | Levels 0–3; deterministic keyword matching |
| Compression | `pipeline/compression/compressor.py` | Paragraph-level; shared regex tokenizer (`utils/tokens.py`); optional |
| Caching | `pipeline/cache/` | Redis; `search:<sha256>`; 1-hour TTL |
| Resilience | `pipeline/resilience/` | Per-dependency retry + circuit breaker |

## Extraction Waterfall

The `ExtractorManager` (`pipeline/crawler/manager.py`) runs three extractors in priority order on each fetched page. After each extraction attempt, the result is scored by `score_extraction()` in `pipeline/crawler/quality.py`. If the score meets the acceptance threshold (`minimum_score`), that result is accepted immediately without trying later extractors.

| Priority | Extractor | Input | Notes |
| ---: | --- | --- | --- |
| 1 | `TrafilaturaExtractor` | Raw HTML | Fastest; no browser required |
| 2 | `PlaywrightTrafilaturaExtractor` | JS-rendered HTML | Launches headless Chromium, then runs Trafilatura on the rendered DOM |
| 3 | `ReadabilityExtractor` | Raw HTML | Uses `readability-lxml` + `markdownify`; final fallback |

The quality score is a weighted sum of 7 signals:

| Signal | Weight | What it measures |
| --- | ---: | --- |
| Title present | 0.12 | Whether the extractor found a page title |
| Character count | 0.18 | Total chars vs. target of 1800 |
| Word count | 0.16 | Total words vs. target of 260 |
| Paragraph count | 0.14 | Double-newline-split paragraphs vs. target of 8 |
| Content / HTML ratio | 0.16 | Plain text length ÷ raw HTML length vs. target of 0.20 |
| Link density | 0.12 | Fraction of text inside hyperlinks (lower is better) |
| Navigation ratio | 0.12 | Fraction of text in nav-like elements (lower is better) |

Hard rejection thresholds (result is rejected regardless of weighted score):

| Check | Threshold |
| --- | --- |
| Min characters | 600 |
| Min words | 90 |
| Min paragraphs | 3 |
| Min content/HTML ratio | 0.08 |
| Max link density | 0.30 |
| Max navigation ratio | 0.35 |

If **no extractor** passes the acceptance threshold, the manager keeps the **highest-scoring** result rather than discarding the page entirely. The score is stored as `extraction_confidence` in the document metadata.

## Ranked Crawl Worker Pool

When `crawl_websites=true` and `rank_and_score_deterministically=true`, crawling is managed by `pipeline/ranking/manager.py` using a streaming `asyncio.Queue`-based worker pool:

```
┌─────────────────────────────────────────────────────────────┐
│ Pre-crawl                                                   │
│  1. robots.txt check (concurrent, per-origin, cached)       │
│  2. Candidate filtering:                                    │
│     - Non-HTTP URLs removed                                 │
│     - Blocked domains (social, video, search engines,       │
│       paywalls — 30+ domains in ranking/constants.py)       │
│     - Blocked paths (/login, /privacy, /tag/, /cart, etc.)  │
│     - Blocked extensions (.pdf, .zip, .jpg, .mp4, etc.)     │
│     - Duplicate URLs (normalized: www stripped, trailing /   │
│       removed)                                              │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Worker Pool                                                 │
│                                                             │
│  task_queue  ◄── all filtered candidates loaded at start    │
│  result_queue ◄── workers push completed Documents          │
│                                                             │
│  N = min(CRAWL_MAX_CONCURRENCY, total_candidates) workers   │
│                                                             │
│  Each worker:                                               │
│    1. Dequeue a candidate from task_queue                    │
│    2. Crawl + extract (full waterfall)                       │
│    3. Push resulting Document to result_queue                │
│    4. On exception: push None (prevents deadlock)            │
│                                                             │
│  Orchestrator loop:                                         │
│    while accepted < target AND processed < total:            │
│      doc = await result_queue.get()  # fastest-first        │
│      if doc and quality_score >= MIN_QUALITY_SCORE (0.65):   │
│        accept(doc)                                          │
│      if accepted >= target: break                            │
│                                                             │
│  On break or exhaustion:                                    │
│    cancel all workers → await gather(return_exceptions)      │
│    sort accepted by quality_score desc                       │
│    return top target_documents                               │
└─────────────────────────────────────────────────────────────┘
```

The key advantage over batch crawling: the orchestrator never waits for a full batch to finish. It processes results as they stream in and cancels all remaining workers the moment the target is met, releasing connections and CPU immediately.

## Resilience

### Exponential Backoff + Jitter

Every network call is wrapped in a `RetryExecutor`. Transient exceptions (`TimeoutError`, `ConnectionError`) and HTTP status codes (408, 429, 500–504) trigger retries. Non-transient failures (`PermanentError`, HTTP 4xx other than 408/429) are raised immediately.

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

### Circuit Breaker State Machine

The `CircuitBreaker` class (`pipeline/resilience/circuit_breaker.py`) implements a three-state machine:

```
CLOSED ──(consecutive failures ≥ threshold)──► OPEN
   ▲                                              │
   │                                    (recovery_timeout elapses)
   │                                              ▼
   └──────────(probe succeeds)────────── HALF_OPEN
                                              │
                                   (probe fails → back to OPEN)
```

- **CLOSED** — normal operation. Every failure increments a counter; every success resets it.
- **OPEN** — all calls are rejected instantly with `CircuitOpenError` (no network traffic).
- **HALF_OPEN** — after `recovery_timeout` seconds, **one** probe call is allowed through (guarded by `asyncio.Lock`). Success → CLOSED. Failure → OPEN.

#### Breaker configuration policies

Policies are defined in `pipeline/resilience/policies.py`:

| Policy | Failure threshold | Recovery timeout |
| --- | ---: | ---: |
| `FAST_PROVIDER_BREAKER` | 5 | 20 s |
| `SLOW_PROVIDER_BREAKER` | 3 | 60 s |

#### Per-dependency breaker instances

Each dependency creates its own `CircuitBreaker` instance, most inheriting thresholds from the policies above:

| Breaker instance | Defined in | Wraps | Inherits from |
| --- | --- | --- | --- |
| `SEARXNG_BREAKER` | `pipeline/retrieval/searxng.py` | SearXNG search calls | `FAST_PROVIDER_BREAKER` |
| `ROBOTS_BREAKER` | `pipeline/retrieval/robots.py` | robots.txt fetches | `FAST_PROVIDER_BREAKER` |
| `CRAWLER_BREAKER` | `pipeline/crawler/fetcher.py` | Page crawl fetches | `FAST_PROVIDER_BREAKER` |
| `REDIS_BREAKER` | `pipeline/cache/cache.py` | Redis get/set/delete | Own config (threshold=10, timeout=10 s) |

Tavily, Brave, and DuckDuckGo providers handle errors internally (returning empty `SearchResults`) and are not wrapped by circuit breakers.

### Graceful Shutdown

`ShutdownManager` (`pipeline/resilience/shutdown.py`, registered in FastAPI lifespan):
1. Cancels all registered background `asyncio.Task`s and awaits them with `return_exceptions=True`
2. Runs cleanup callbacks in **reverse** registration order (LIFO)
3. Closes the shared HTTPX client
4. Closes the Redis client

Shutdown is idempotent — an `asyncio.Lock` + boolean flag prevent double-shutdown.

## Middleware & Metrics

### Rate Limiting

`api/middleware/rate_limit.py` — `conditional_rate_limit`:
- Uses `fastapi-limiter` + Redis
- **30 requests / 60 seconds** per client
- Requests with header `x-benchmark: true` bypass the limiter (for the benchmark runner)

### Prometheus Metrics (`api/metrics.py`)

| Metric | Type | Description |
| --- | --- | --- |
| `quarry_search_cache_hits_total` | Counter | Responses served from Redis cache |
| `quarry_cache_lookup_ms` | Histogram | Time spent on cache reads |
| `quarry_urls_found_total` | Counter | Candidate URLs from all providers |
| `quarry_pages_crawled_total` | Counter | Pages successfully crawled |
| `quarry_crawl_failures_total` | Counter | Pages that failed to crawl |
| `quarry_compression_ratio` | Histogram | Distribution of byte-level compression ratios |
| `quarry_tokens_saved_total` | Counter | Tokens removed by compression |

FastAPI HTTP metrics (latency, status codes, request counts) are additionally exposed by `prometheus-fastapi-instrumentator` at `GET /metrics`.

### File-based Logging

In addition to stdout, Quarry writes structured, timestamped logs to the `logs/` directory (`config/logging.py`). A new log file is created on startup (e.g., `2026-08-09_07-18-00.log`).

## Schemas (Pydantic v2)

### `SearchRequest`

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `query` | `str` | required | Search query |
| `format` | `FlexibleFormatting` | `default` | `default` · `text_only` · `content_only` · `url_only` |
| `cleaning_level` | `CleaningLevel` (0–3) | `0` | Cleaning intensity |
| `crawl_websites` | `bool` | `false` | Fetch and extract pages |
| `enable_caching` | `bool` | `false` | Read/write Redis cache |
| `compress_output` | `bool` | `false` | Run compression after cleaning |
| `target_token_budget` | `int \| null` | `null` | Per-document token limit (default 2048) |
| `target_documents` | `int` | `10` | Stop ranked crawl after N quality docs |
| `enhance_query` | `bool` | `false` | Normalise query before retrieval |
| `rank_and_score_deterministically` | `bool` | `false` | Queue-based ranked crawling |
| `time_range` | `day\|week\|month\|year\|null` | `null` | SearXNG recency filter |
| `language` | `str \| null` | `null` | SearXNG language |
| `engines` | `list[str]` | `[]` | SearXNG engine filter |
| `categories` | `list[str]` | `[]` | SearXNG category filter |

### `SearchResponse`

```
SearchResponse
├── success: bool
├── request_id: str          # UUID per request (not per process)
├── query: str               # normalised query
├── timings: SearchTimings   # per-stage latencies (ms)
├── benchmark: SearchBenchmark
│   ├── cache_hit / cache_lookup_ms / cache_write_ms
│   ├── urls_found / crawlable_urls / urls_filtered_out
│   ├── pages_successfully_crawled / crawl_failures / average_crawl_depth
│   ├── bytes_before / bytes_after
│   ├── tokens_before / tokens_after
│   ├── compression_ratio (property)
│   └── token_reduction_ratio (property)
└── [ONE of the following, based on format]
    ├── documents: list[CleanDocument]   # format=default
    ├── formatted_content: str           # format=text_only | content_only
    └── urls: list[str]                  # format=url_only
```

`None` fields are stripped from the response by `response_model_exclude_none=True`.

## Tests

```
tests/
├── unit/
│   ├── test_cleaner.py          # Cleaning level transformations
│   ├── test_compressor.py       # Token-budget compression
│   ├── test_crawler.py          # Extraction waterfall, quality scoring, fallback docs
│   ├── test_openapi_docs.py     # OpenAPI schema generation
│   ├── test_ranking_flow.py     # Queue-based ranked crawl orchestration
│   ├── test_searxng.py          # SearXNG result normalisation
│   └── test_tokens.py           # Token estimator
├── integration/
│   └── test_search_api.py       # Full FastAPI route with monkeypatched pipeline
└── datasets/
    ├── easy_queries.txt
    ├── medium_queries.txt
    └── hard_queries.txt         # Used by the benchmark runner
```

Run all tests:

```bash
uv run pytest
```

Run with coverage:

```bash
uv run pytest --cov=api --cov=pipeline --cov=models --cov-report=term-missing
```

## Benchmark

`scripts/benchmark.py` runs three configurations against three query difficulty tiers:

| Config | Description |
| --- | --- |
| `baseline` | Crawl + rank, no cache, no compression |
| `cache_on` | Crawl + rank + cache + query normalisation |
| `compression_1048_cache_off` | Crawl + rank + compress to 1048 tokens |

Each run reports:

```json
{
  "requests": 10,
  "success_rate": 1.0,
  "avg_latency": 4231.5,
  "p50": 4100,
  "p95": 6800,
  "p99": 7200,
  "cache_hit_rate": 0.0,
  "avg_token_reduction_pct": 38.2
}
```

To bypass rate limiting during benchmarks, the runner sets `x-mode: benchmark` on each request (handled by the API's conditional limiter via the `x-benchmark: true` header pattern).

## Benchmark Results

Measured across two independent runs (10 requests per tier × config, 90 requests per run) against live Tavily + SearXNG:

| Tier | Config | p50 Latency | Cache Hit Rate | Avg Token Reduction |
| --- | --- | ---: | ---: | ---: |
| Easy | `baseline` | 32.0 – 39.7 s | 0% | 0.5 – 1.5% |
| Easy | `cache_on` | 3.8 – 4.2 ms | 100% | 1.7 – 2.7% |
| Easy | `compression_1048_cache_off` | 17.9 – 35.1 s | 0% | 50.9 – 57.0% |
| Medium | `baseline` | 13.3 – 13.5 s | 0% | 0.1 – 0.7% |
| Medium | `cache_on` | 4.0 ms – 15.2 s* | 90 – 100% | 0.9 – 1.4% |
| Medium | `compression_1048_cache_off` | 12.1 – 16.7 s | 0% | 67.3 – 72.0% |
| Hard | `baseline` | 15.7 – 35.3 s | 0% | 0.2 – 1.0% |
| Hard | `cache_on` | 3.7 – 4.6 ms | 100% | 0.3 – 0.7% |
| Hard | `compression_1048_cache_off` | 12.0 – 13.7 s | 0% | 68.6 – 76.1% |

**Headline numbers:**
- **p50 latency drops by >99.9%** on cache hit (13,000–48,000 ms cold → ~4 ms cached).
- **Token reduction reaches 50–76%** at a 1048-token budget, scaling with document length (harder/longer-form queries compress more).
- **179 / 180 requests succeeded** across both runs (99.4% aggregate success rate) against live, uncontrolled web targets.

\* One `medium | cache_on` run recorded a 15.2 s p50 despite a 90% cache hit rate — likely a single cold miss or cache warm-up race skewing a 10-request sample. Tracked under the Stage-Level Caching and SearXNG stability roadmap items.

Raw JSON output from `scripts/benchmark.py` for all 9 tier × config combinations is available on request or reproducible locally via the [Running the Benchmark](docs/benchmark.md#running-the-benchmark) instructions.

## CI / CD Pipelines

| Workflow | Trigger | Steps |
| --- | --- | --- |
| `ci.yml` | push/PR to `main` | uv install → Ruff → Black → Pytest (with Redis + SearXNG services) |
| `docker.yml` | push/PR to `main` | Build and push API Docker image |
| `codeql.yml` | push/PR to `main` | GitHub CodeQL security scan |
| `benchmark.yml` | push/PR to `main` + manual | Full benchmark suite with live Tavily + SearXNG |

The benchmark workflow validates `TAVILY_API_KEY` and runs `scripts/benchmark.py` against a live API process.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `SEARXNG_BASE_URL` | `http://localhost:8080` | SearXNG instance URL |
| `SEARXNG_TIMEOUT_SECONDS` | `20` | SearXNG request timeout |
| `CRAWL_TIMEOUT_SECONDS` | `15` | Per-page crawl timeout |
| `CRAWL_MAX_CONCURRENCY` | `5` | Max concurrent crawler workers |
| `REDIS_URL` | `redis://redis:6379/0` | Redis for rate limiting + cache |
| `GRAFANA_ADMIN_PASSWORD` | `quarry_admin` | Grafana admin password |
| `TAVILY_API_KEY` | — | Tavily search API key (benchmark CI secret) |

Hard-coded client defaults (not env-overridable):

| Setting | Value |
| --- | --- |
| User-Agent | `QuarryBot/0.6` |
| HTTP timeout | 30 s |
| Max connections | 100 |
| Keep-alive connections | 20 |

## Project Layout

```
quarry/
├── api/
│   ├── app.py              # FastAPI app, lifespan, Prometheus instrument
│   ├── metrics.py          # Custom prometheus_client counters + histograms
│   ├── middleware/
│   │   └── rate_limit.py   # Conditional Redis-backed rate limiter
│   └── routes/
│       └── search.py       # POST /search — pipeline call + metric emission
├── config/
│   ├── logging.py          # JSON structured logging
│   └── settings.py         # Frozen dataclass from env vars
├── models/
│   ├── document.py         # Document, Documents
│   ├── clean_document.py   # CleanDocument, CleanDocuments
│   └── search.py           # SearchRequest, SearchResponse, SearchBenchmark, SearchTimings, …
├── pipeline/
│   ├── pipeline.py         # Top-level orchestration
│   ├── cache/              # Redis get/set/make_key
│   ├── cleaning/           # cleaner.py, steps.py
│   ├── compression/        # compressor.py
│   ├── crawler/            # crawler.py, fetcher.py, manager.py, quality.py, extractors/
│   ├── http/               # Shared httpx.AsyncClient lifecycle
│   ├── query/              # Query normaliser
│   ├── ranking/            # Queue-based ranked crawl manager, filters, recall
│   ├── resilience/         # RetryPolicy, CircuitBreaker, ShutdownManager, policies
│   └── retrieval/          # searxng.py, tavily.py, brave.py, duckduckgo.py, robots.py
├── scripts/
│   └── benchmark.py        # Async benchmark runner
├── tests/
│   ├── unit/               # Component-level tests
│   ├── integration/        # FastAPI TestClient tests
│   └── datasets/           # Query difficulty tiers
├── docker/
│   └── searxng/settings.yml
├── docker-compose.yml       # API + SearXNG + Redis + Prometheus + Grafana
├── docker-compose.dev.yml
├── Dockerfile
├── prometheus.yml           # scrape_interval: 10s → api:8000
└── pyproject.toml           # uv / setuptools / ruff / black / pytest config
```

## Stage Documentation

- [Search API](docs/search-api.md) — request fields, response shape, curl example
- [Request Flow](docs/request-flow.md) — full lifecycle sequence diagram
- [Retrieval](docs/retrieval.md) — fallback chain, SearXNG parameters, normalisation
- [Crawling](docs/crawling.md) — fetch, extractor waterfall, quality scoring, ranked mode
- [Cleaning](docs/cleaning.md) — level-to-step mapping
- [Compression](docs/compression.md) — paragraph budget algorithm
- [Caching](docs/caching.md) — Redis key construction, TTL, circuit breaker
- [Resilience & Observability](docs/resilience-observability.md) — retry policies, circuit breakers, shutdown, metrics
- [Testing](docs/testing.md) — unit/integration test structure, coverage, CI config
- [Benchmark](docs/benchmark.md) — benchmark script, configurations, CI workflow, result interpretation

## Project Roadmap

Future development is focused on **speed, stability, and retrieval quality**.

### Phase 1: Core Stability & Architecture

- [ ] **Stage-Level Caching**  
  Introduce granular caching between pipeline stages (e.g., raw HTML, cleaned content) to:
  - Reduce redundant computation  
  - Accelerate debugging  
  - Improve repeated query performance  

- [ ] **SearXNG Stability Upgrades**  
  Add:
  - Strict timeouts  
  - Automated fallback triggers  
  - Circuit breakers  
  to handle failures in internal SearXNG instances.

- [ ] **Codebase Refactoring & Tech Debt**  
  - Improve modular architecture  
  - Expand type hinting coverage  
  - Remove legacy code paths  
  - Prepare for open-source contributions  

### Phase 2: Performance & Speed

- [ ] **Crawling Concurrency Optimization**  
  Redesign async crawling pipeline to:
  - Maximize parallel fetch throughput  
  - Eliminate I/O bottlenecks  
  - Improve overall latency  

- [ ] **Streaming API Responses (SSE)**  
  Implement Server-Sent Events to:
  - Stream results per document  
  - Reduce Time-To-First-Byte (TTFB)  
  - Improve perceived responsiveness  


### Phase 3: Advanced Capabilities

- [ ] **Semantic Query Understanding**  
  Upgrade query normalization to:
  - Capture intent (not just keywords)  
  - Improve upstream search relevance  

- [ ] **Custom Extraction Targeting**  
  Allow users to pass:
  - CSS selectors  
  - JSON paths  

  Enables precise extraction from known layouts, bypassing generic pipelines.

- [ ] **Summarization & Context Headroom**  
  Add lightweight local summarization to:
  - Dynamically fit content into token limits  
  - Optimize context usage for downstream LLMs  

- [ ] **Vector-Based Search Integration**  
  Enable optional RAG support:
  - Embed extracted chunks  
  - Store in vector DB  
  - Enable semantic retrieval  


### Phase 4: Ecosystem & Deployment

- [ ] **Hosted Deployment & Observability**  
  Launch managed Quarry service with:
  - Cloud-hosted API  
  - Real-time logging & metrics  
  - Tracing and analytics dashboards  
  - Enterprise-grade observability  


## Vision

Quarry aims to become the **default retrieval layer for LLM applications**—a deterministic, efficient, and production-grade bridge between the chaotic web and structured AI context.

## Design Decisions

Some decisions I took while creating this project:

### Why call Tavily → SearXNG → Brave → DuckDuckGo one after another instead of hitting them all at once?

Because most requests don't need all four. Each provider has its own cost and rate-limit profile, Tavily especially, since it's a paid API, so firing them all in parallel would mean paying for and waiting on providers you didn't even need. The chain only moves to the next provider if the current results fall short of the target document count, and each call is wrapped in its own try/except so one provider going down doesn't take the others with it.

### Why deterministic, rule-based cleaning instead of just having an LLM clean up the markdown?

Because Quarry's whole job is to hand reliable context to an LLM further down the pipeline and an LLM cleaning step would undermine that. Run the same page through it twice and you might get two different outputs, plus you're burning tokens cleaning content before you've even used it. Rule-based transformations at fixed cleaning levels (0–3) are boring in the best way: same input, same output, every time, with clean metrics on exactly how much was trimmed.

### Why a worker pool that cancels itself early instead of just crawling every candidate URL?

Because most candidate URLs turn out to be junk, and crawling them anyway is just wasted time and bandwidth. Instead, workers pull from a queue and stream results back as they finish extracting. The moment enough documents clear the quality bar, the rest of the workers get cancelled. So the time a request takes tracks "how fast we found good pages," not "how many pages exist."

### Why cache the whole response instead of caching individual documents?

A full-response cache hit means skipping retrieval, crawling, cleaning, and compression in one Redis lookup — about as cheap as a cache can get. Caching at the document level would still leave ranking, compression, and formatting to redo on every request. The catch is staleness, which is why entries expire after an hour, and the cache key is built off the *normalized* query and sorted params rather than the raw string — so near-duplicate queries still land on the same cached response. I do plan on caching individual steps so Quarry is able to speed up the flow without the cost of 

### Why trim to a token budget and dedupe paragraphs instead of just summarizing with an LLM?

Same logic as the cleaning step: determinism and cost. An LLM summary adds latency, adds cost on every cache miss, and — worse — can quietly change the actual wording of the source. If the thing reading this output later needs to quote or verify a fact from the page, you don't want a summarizer's paraphrase in the way. Budget-based trimming and paragraph dedup shrink the content without touching what it actually says. I also plan on adding [Headroom](https://github.com/headroomlabs-ai/headroom) summarizer that can be used if one wishes to.
