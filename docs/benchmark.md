# Benchmark Guide

`scripts/benchmark.py` measures Quarry's end-to-end latency, cache efficiency,
and compression performance across three query difficulty tiers and three
pipeline configurations.

## Running the Benchmark

The benchmark requires a running Quarry stack:

```bash
# Start the full stack
docker compose up --build -d

# Run the benchmark (connects to localhost:8000)
uv run python scripts/benchmark.py
```

The runner sends requests with `x-mode: benchmark` in the header, which is
read by the route handler for instrumentation purposes. To bypass the rate limiter
during benchmarks, the runner relies on the fact that `CRAWL_MAX_CONCURRENCY`
limits internal parallelism rather than the API rate limit; a concurrency of 2
is enforced client-side via `asyncio.Semaphore(2)` in the script.

## Query Tiers

| Tier | File | Characteristics |
| --- | --- | --- |
| `easy` | `tests/datasets/easy_queries.txt` | Short, common queries; high Tavily hit rate |
| `medium` | `tests/datasets/medium_queries.txt` | Multi-word, specific queries |
| `hard` | `tests/datasets/hard_queries.txt` | Long, niche, or ambiguous queries |

## Benchmark Configurations

| Config name | `enable_caching` | `crawl_websites` | `rank_and_score_deterministically` | `compress_output` | `target_token_budget` |
| --- | :---: | :---: | :---: | :---: | ---: |
| `baseline` | ✗ | ✓ | ✓ | ✗ | — |
| `cache_on` | ✓ | ✓ | ✓ | ✗ | — |
| `compression_1048_cache_off` | ✗ | ✓ | ✓ | ✓ | 1048 |

All configs use `cleaning_level: 1` and `target_documents: 2`.

The `cache_on` config performs a **cache warm-up** pass before the timed run,
so the measured latencies reflect cache-hit performance.

## Output Format

Each tier × config combination prints a summary:

```json
{
  "requests": 10,
  "success_rate": 1.0,
  "avg_latency": 4231.5,
  "p50": 4100.0,
  "p95": 6800.0,
  "p99": 7200.0,
  "cache_hit_rate": 0.0,
  "avg_token_reduction_pct": 38.2
}
```

| Field | Description |
| --- | --- |
| `requests` | Total requests sent |
| `success_rate` | Fraction with `success: true` in response |
| `avg_latency` | Mean end-to-end wall time (ms) |
| `p50 / p95 / p99` | Latency percentiles across successful requests |
| `cache_hit_rate` | Fraction of requests where `benchmark.cache_hit=true` |
| `avg_token_reduction_pct` | Mean `(tokens_before - tokens_after) / tokens_before × 100` |

## CI Benchmark Workflow (`.github/workflows/benchmark.yml`)

The benchmark runs automatically on every push/PR to `main` and can be
triggered manually via `workflow_dispatch`.

### Steps

1. **Checkout** + **uv install** — installs all dependencies from the lockfile.
2. **Start SearXNG** — spins up a Docker container with a minimal `settings.yml`
   that enables the `json` format.
3. **Verify Tavily API key** — validates `TAVILY_API_KEY` is present (from
   GitHub repository secrets) and tests a direct Tavily API call.
4. **Wait for SearXNG** — polls `http://127.0.0.1:8080` up to 60 times.
5. **Debug SearXNG** — issues a test JSON query and logs the first 1000 bytes.
6. **Start Quarry API** — launches `uvicorn` in the background; polls
   `GET /health` up to 60 times.
7. **Run benchmark** — `uv run python scripts/benchmark.py`.
8. **Teardown** — `pkill -f uvicorn` ensures the process doesn't outlive the job.
9. **Show logs** — always prints `uvicorn.log` for debugging.

### Required Secrets

| Secret | Description |
| --- | --- |
| `TAVILY_API_KEY` | Tavily search API key — used by the retrieval chain |

### Environment Variables

```yaml
REDIS_URL: redis://127.0.0.1:6379/0
TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
SEARXNG_BASE_URL: http://127.0.0.1:8080
```

## Interpreting Results

- **High `p99` vs `p50`** — indicates occasional slow pages in the crawl pool.
  Try increasing `CRAWL_TIMEOUT_SECONDS` or reducing `target_documents`.
- **Low `success_rate`** — check Tavily API key validity and SearXNG availability.
- **`cache_hit_rate < 1.0` on `cache_on`** — the warm-up may have failed or the
  Redis TTL is shorter than expected; verify Redis connectivity.
- **High `avg_token_reduction_pct`** — compression is working effectively.
  Values above 50% at budget 1048 are expected for long articles.
