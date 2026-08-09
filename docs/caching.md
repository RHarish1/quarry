# Caching Stage

Quarry caches completed, non-empty search responses in Redis when a request
sets `enable_caching: true`. Implementation: `pipeline/cache/`.

## Redis Connection

`get_redis()` creates one module-level asynchronous Redis client from `REDIS_URL`
with `decode_responses=True`. The default URL is `redis://redis:6379/0` (the
Docker Compose service). The API initialises this client during startup — it is
also given to `fastapi-limiter` for rate limiting — and closes it during shutdown.

Redis must therefore be reachable even when `enable_caching` is `false`.

## Cache Key Construction

Keys have the form `search:<sha256>`. The SHA-256 digest is derived from the
serialised request **after** these normalisations:

1. `enable_caching` field is excluded.
2. `query` is lowercased and whitespace-collapsed.
3. `engines` and `categories` lists are sorted (order does not affect cache hits).

All other request fields (`format`, `cleaning_level`, `crawl_websites`,
`compress_output`, `target_token_budget`, `target_documents`, `enhance_query`,
`rank_and_score_deterministically`, `time_range`, `language`) participate in the key.

## Read / Write Lifecycle

```
Request arrives
  └─► enable_caching=true?
        └─► make_cache_key(request)
        └─► GET search:<sha256>
              ├─► HIT  → deserialise SearchResponse → set cache_hit=true → return
              └─► MISS → run full pipeline
                            └─► non-empty result?
                                  └─► SET search:<sha256> EX 3600
```

A response is cached only when at least one of `documents`, `formatted_content`,
or `urls` is non-empty (i.e., the pipeline produced actual content).

Cache entries expire after **3,600 seconds** (1 hour).

## Resilience

Redis operations (read, write) pass through:

- **`REDIS_RETRY`** policy: 2 retries, 100 ms base, 1 s max, ±50 ms jitter,
  retries only `TimeoutError` and `ConnectionError`.
- **`REDIS_BREAKER`** circuit breaker: opens after 5 failures, 15-second
  recovery timeout.

A cache failure is not fatal. The route-level exception handler catches it and
returns an empty `SearchResponse` with zero timings rather than an HTTP error.

## Benchmark Instrumentation

The pipeline records:

| `SearchBenchmark` field | Description |
| --- | --- |
| `cache_hit` | `true` if the response was served from cache |
| `cache_lookup_ms` | Wall time of the `GET` call |
| `cache_write_ms` | Wall time of the `SET` call |

These fields are also reflected in Prometheus:
- `quarry_search_cache_hits_total` incremented on hit
- `quarry_cache_lookup_ms` observed on every lookup
