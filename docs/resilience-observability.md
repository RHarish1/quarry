# Resilience and Observability

Quarry shares a single asynchronous HTTPX client across SearXNG retrieval,
robots.txt checks, and page fetching. The client is created during FastAPI
startup and closed during graceful shutdown. It follows redirects, uses the
`QuarryBot/0.3` user agent, applies a 30-second default timeout, and is limited
to 100 connections with 20 keep-alive connections.

## Retry Policies

Retries use exponential backoff plus random jitter. They apply to configured
timeout and connection failures; non-transient failures are raised immediately.

| Dependency | Retry attempts after the initial call | Base delay | Maximum delay |
| --- | ---: | ---: | ---: |
| SearXNG | 3 | 250 ms | 2 s |
| Page crawler | 2 | 500 ms | 4 s |
| Redis | 2 | 100 ms | 1 s |
| robots.txt | 3 (default policy) | 500 ms | 8 s |

## Circuit Breakers

SearXNG, crawling, robots.txt, and Redis each have a circuit breaker. A breaker
records failures, opens after its configured threshold, and rejects additional
calls until its recovery timeout has elapsed. It then permits one half-open
probe; a successful probe closes and resets the breaker, while a failed probe
reopens it.

| Dependency | Failure threshold | Recovery timeout |
| --- | ---: | ---: |
| SearXNG | 5 | 20 s |
| Page crawler | 5 | 20 s |
| robots.txt | 5 | 20 s |
| Redis cache helper | 10 | 10 s |

## Graceful Shutdown

The shutdown manager cancels registered background tasks, runs registered
cleanup callbacks in reverse order, closes the shared HTTP client, and closes
the Redis client. Shutdown is idempotent, so repeated shutdown signals do not
run cleanup twice.

## Internal Benchmark Instrumentation

Each pipeline execution creates an internal `SearchBenchmark`. It tracks cache
lookup/write time and hit state, candidate counts, crawl counters, byte/token
counts before and after cleaning/compression, and the response timing bundle.
This object is currently used inside the pipeline only: it is neither returned
by `POST /search` nor persisted or exported.

The public `SearchResponse` includes `request_id`, `query`, `timings`, and
`documents`. `request_id` identifies the API process that handled the request;
it is assigned when the route module loads, not newly generated for each call.
