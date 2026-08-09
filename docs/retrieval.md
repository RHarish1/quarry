# Retrieval Stage

The retrieval stage turns a `SearchRequest` into a deduplicated list of `SearchResult`
objects. Implemented in `pipeline/retrieval/` and orchestrated by `pipeline/pipeline.py`.

## Multi-Provider Fallback Chain

Quarry uses a sequential fallback strategy. Providers are tried in order; each
provider failure is caught and logged without aborting the chain.

```
1. Tavily       ── always attempted first
        │
        ▼ (if results < target_documents × 2)
2. SearXNG      ── form-encoded POST to SEARXNG_BASE_URL/search
        │
        ▼ (if combined total < target_documents)
3. Brave Search ── Brave Web Search API
        │
        ▼ (if combined total still < target_documents)
4. DuckDuckGo   ── free DDGS client (ddgs library)
```

Results from all providers are concatenated. Duplicates are removed by URL
(first-seen wins, insertion order preserved). If the combined total is zero
after all providers, the pipeline returns an empty `SearchResponse`.

## Provider: SearXNG

When Quarry queries SearXNG it sends a form-encoded `POST` to
`{SEARXNG_BASE_URL}/search` with `format=json` always set.

| Quarry field | SearXNG parameter |
| --- | --- |
| `query` | `q` |
| `categories` | `categories`, comma-separated |
| `language` | `language` |
| `time_range` | `time_range` |
| `engines` | `engines`, comma-separated |

All requests use the startup-created shared HTTPX client (30 s timeout,
`QuarryBot/0.6` user agent, follows redirects).

## Result Normalisation

Each provider result is normalised into a `SearchResult`:

```python
SearchResult(
    url="https://...",
    title="...",
    content="...",   # snippet text
    metadata={...},  # all extra provider fields preserved
)
```

Malformed items (missing URL/title/content) are skipped silently. SearXNG
responses that contain a non-list `results` field produce an empty result set.

## Resilience

SearXNG calls are wrapped in `SEARCH_PROVIDER_RETRY` (3 retries, 250 ms base,
2 s max, exponential backoff + jitter) and `FAST_PROVIDER_BREAKER` (opens after
5 failures, 20-second recovery). Other providers have analogous wrapping.

Connection failures, timeouts, non-2xx responses, and JSON parse errors are
represented as exceptions. They cause the provider to be skipped in the fallback
chain rather than aborting the request.

## robots.txt (`pipeline/retrieval/robots.py`)

robots.txt is checked **only in ranked crawl mode** (`rank_and_score_deterministically=true`).
Quarry fetches and caches each origin's `robots.txt` for `QuarryBot/0.6`:

- **Missing file** → crawling allowed.
- **Fetch or parse error** → origin skipped conservatively.
- **Disallowed path** → URL removed before crawling begins.
