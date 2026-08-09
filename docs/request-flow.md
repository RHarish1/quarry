# Request Flow

Complete lifecycle of a `POST /search` request. Implemented in `api/app.py`,
`api/routes/search.py`, and `pipeline/pipeline.py`.

```mermaid
sequenceDiagram
  participant C  as Client
  participant A  as FastAPI route
  participant RL as Rate limiter (Redis)
  participant P  as Pipeline orchestrator
  participant R  as Redis cache
  participant T  as Tavily
  participant SX as SearXNG
  participant BR as Brave Search
  participant DG as DuckDuckGo
  participant H  as Shared HTTPX client
  participant RB as robots.txt (ranked mode)
  participant W  as Crawler workers
  participant EM as Extractor manager
  participant CL as Cleaner
  participant CO as Compressor
  participant M  as Prometheus metrics

  C->>A: POST /search (JSON body)
  A->>A: Pydantic validation → SearchRequest
  A->>A: Generate request_id = uuid4()
  A->>RL: conditional_rate_limit (skip if x-benchmark: true)
  RL->>R: INCR + TTL (30 req / 60 s)
  RL-->>A: 429 if exceeded

  opt enhance_query=true
    A->>P: normalize_query(request)
    P-->>A: normalized SearchRequest
  end

  opt enable_caching=true
    A->>R: GET search:<sha256>
    R-->>A: cached SearchResponse (cache hit → return immediately)
  end

  Note over P: Retrieval chain — sequential fallback
  P->>T: search_tavily(query)
  T-->>P: SearchResults (or exception → skip)
  opt Tavily results < target_documents × 2
    P->>SX: search_searxng(request)
    SX-->>P: SearchResults (or exception → skip)
  end
  opt combined < target_documents
    P->>BR: search_brave(query)
    BR-->>P: SearchResults (or exception → skip)
  end
  opt combined still < target_documents
    P->>DG: search_duckduckgo(query)
    DG-->>P: SearchResults (or exception → skip)
  end
  P->>P: Deduplicate URLs (first-seen wins)

  alt crawl_websites=false
    P->>P: Convert snippets → Documents (crawl_status: skipped)
  else crawl_websites=true, rank_and_score_deterministically=true
    P->>H: fetch robots.txt per origin
    P->>P: filter_candidates (blocked, dupes, extensions, noise paths)
    P->>W: spawn N workers (asyncio.Queue)
    loop until accepted ≥ target_documents OR queue empty
      W->>H: fetch page HTML
      H-->>W: RawDocument
      W->>EM: extract(RawDocument)
      EM->>EM: TrafilaturaExtractor → score
      EM->>EM: PlaywrightTrafilaturaExtractor → score (if needed)
      EM->>EM: ReadabilityExtractor → score (if needed)
      EM-->>W: best ExtractedDocument
      W->>W: quality_score ≥ MIN_QUALITY_SCORE?
      W-->>P: Document (accepted or fallback)
    end
    P->>W: cancel remaining workers
    P->>P: sort by quality_score desc, slice to target_documents
  else crawl_websites=true, rank_and_score_deterministically=false
    P->>H: fetch all results concurrently (semaphore)
    H-->>P: Documents
  end

  P->>CL: clean_documents(CleanRequest)
  CL-->>P: CleanDocuments + metrics

  opt compress_output=true
    P->>CO: compress_documents(CleanDocuments, token_budget)
    CO-->>P: compressed CleanDocuments
  end

  P->>P: format output (default / text_only / content_only / url_only)

  opt enable_caching=true AND non-empty result
    P->>R: SET search:<sha256> EX 3600
  end

  P-->>A: SearchResponse
  A->>M: emit Prometheus metrics from benchmark
  A-->>C: SearchResponse (None fields stripped)
```

## 1. Application Startup

FastAPI runs its lifespan context before accepting any requests:

1. `create_http_client()` — creates one `httpx.AsyncClient` (100 connections,
   20 keep-alive, 30 s timeout, `QuarryBot/0.6` user agent).
2. `get_redis()` + `FastAPILimiter.init(redis)` — initialises the rate limiter.
3. `shutdown_manager.register_cleanup(close_http_client)` and `register_cleanup(close_redis)`.

## 2. Rate Limiting

`conditional_rate_limit` in `api/middleware/rate_limit.py`:

- 30 requests per 60 seconds per client (Redis-backed via `fastapi-limiter`).
- Requests with header `x-benchmark: true` bypass the limiter entirely. This
  allows `scripts/benchmark.py` to run without exhausting quotas.

HTTP `429` is returned when the limit is exceeded.

## 3. Request ID

A fresh `uuid4()` is generated **inside the route handler** for every request.
This guarantees uniqueness across concurrent requests and worker processes.

## 4. Optional Query Normalisation

When `enhance_query=true`, `normalize_query(request)` applies deterministic
transformations before anything hits the network:

- Unicode NFKC normalisation
- Curly-quote and dash normalisation
- Lowercase
- Punctuation stripping
- Whitespace collapse
- Consecutive duplicate token removal

## 5. Cache Read

When `enable_caching=true`, the pipeline builds `search:<sha256>` (excluding
`enable_caching`, normalising the query, sorting lists) and issues a Redis `GET`.
A hit returns the stored `SearchResponse` immediately — retrieval, crawling,
cleaning, and compression are skipped entirely.

## 6. Retrieval Chain

Quarry runs providers sequentially, each guarded by its own try/except:

| Step | Provider | Trigger condition |
| --- | --- | --- |
| 1 | Tavily | Always |
| 2 | SearXNG | Tavily results < `target_documents × 2` |
| 3 | Brave | Combined total < `target_documents` |
| 4 | DuckDuckGo | Combined total still < `target_documents` |

Results are concatenated and deduplicated (URL, first-seen wins). If all
providers fail or the combined total is zero, the pipeline returns an empty
`SearchResponse` with the measured search latency.

## 7. Crawling and Extraction

### Snippet path (`crawl_websites=false`)

Each `SearchResult` becomes a `Document` with `crawl_status: "skipped"` and
no network calls are made.

### Standard crawl (`crawl_websites=true`, `rank_and_score_deterministically=false`)

All results are fetched concurrently, bounded by `asyncio.Semaphore(CRAWL_MAX_CONCURRENCY)`.
Fetch or extraction failures produce fallback documents preserving the snippet.

### Ranked crawl (`crawl_websites=true`, `rank_and_score_deterministically=true`)

Pre-crawl: robots.txt check → candidate filter.  
During crawl: `asyncio.Queue`-based worker pool streams results as they complete.
The orchestrator accepts documents with `quality_score ≥ MIN_QUALITY_SCORE` and
cancels all workers the moment `target_documents` are accepted.

## 8. Cleaning

`clean_documents` converts every `Document` to a `CleanDocument` at the
requested `cleaning_level` (0–3). Metrics (token counts, reduction %, latency,
applied steps) are recorded per document.

## 9. Compression (optional)

When `compress_output=true`, the compressor runs paragraph-level deduplication
and budget trimming on each `CleanDocument`. `target_token_budget` (default 2048)
controls the per-document limit (estimated at 4 chars/token).

## 10. Output Formatting

The pipeline selects exactly one payload field based on `format`:

| `format` | Populated field | Content |
| --- | --- | --- |
| `default` | `documents` | `list[CleanDocument]` |
| `text_only` | `formatted_content` | Title + URL + markdown per doc, joined by `---` |
| `content_only` | `formatted_content` | Markdown only, joined by blank lines |
| `url_only` | `urls` | `list[str]` of document URLs |

`response_model_exclude_none=True` strips the two unpopulated fields from the
JSON response automatically.

## 11. Cache Write

When `enable_caching=true` and the response contains non-empty content, the
`SearchResponse` is serialised and stored at `search:<sha256>` with a 3600-second TTL.

## 12. Prometheus Emission

After the pipeline completes, the route handler emits metrics from
`response.benchmark`:

```python
if benchmark.cache_hit:         SEARCH_CACHE_HITS.inc()
URLS_FOUND.inc(benchmark.urls_found)
PAGES_CRAWLED.inc(benchmark.pages_successfully_crawled)
CRAWL_FAILURES.inc(benchmark.crawl_failures)
TOKENS_SAVED.inc(benchmark.tokens_before - benchmark.tokens_after)
CACHE_LOOKUP_MS.observe(benchmark.cache_lookup_ms)
COMPRESSION_RATIO.observe(benchmark.compression_ratio)
```

## Error Handling

| Failure | Behaviour |
| --- | --- |
| Retrieval total = 0 | Return empty `SearchResponse`; `success=false` |
| Crawl stage exception | Return empty response with search + crawl timings |
| Cleaning stage exception | Return empty response with search + crawl + cleaning timings |
| Compression exception | Return **uncompressed** cleaned documents; log the error |
| Unhandled route exception | Return empty response with `total_request_latency_ms` only |
