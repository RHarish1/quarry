# Search API

`POST /search` accepts a `SearchRequest` body and returns a `SearchResponse`
object. It searches SearXNG, optionally crawls the returned URLs, and cleans
the resulting documents. The endpoint is rate limited to 30 requests per 60
seconds using Redis.

## Request

```json
{
  "query": "FastAPI lifespan",
  "cleaning_level": 1,
  "crawl_websites": true,
  "enable_caching": true,
  "compress_output": true,
  "target_token_budget": 2048,
  "target_documents": 10,
  "enhance_query": true,
  "rank_and_score_deterministically": true,
  "language": "en",
  "engines": ["google"],
  "categories": ["general"]
}
```

`query` is required. All other fields are optional.

| Field | Default | Description |
| --- | --- | --- |
| `cleaning_level` | `0` | Cleaning intensity, from `0` to `3`. |
| `crawl_websites` | `false` | Whether to crawl candidate result URLs. |
| `enable_caching` | `false` | Cache non-empty responses in Redis for one hour. |
| `compress_output` | `false` | Apply deterministic compression after cleaning. |
| `target_token_budget` | `null` | Per-document compression budget; uses `2048` when compression is enabled without a value. Must be positive. |
| `target_documents` | `10` | Maximum number of documents selected when deterministic ranking is enabled. |
| `enhance_query` | `false` | Normalize the query before sending it to SearXNG. |
| `rank_and_score_deterministically` | `false` | Filter, crawl, score, and select documents when `crawl_websites` is also true. |
| `time_range` | `null` | One of `day`, `week`, `month`, or `year`. |
| `language` | `null` | Search language. |
| `engines` | `[]` | Search-engine filters. |
| `categories` | `[]` | SearXNG category filters. |

## Example

```bash
curl -X POST http://localhost:8000/search \
  -H 'content-type: application/json' \
  -d '{"query":"FastAPI lifespan","crawl_websites":true}'
```

## Response Shape

- `query`: the effective search query (normalized when `enhance_query` is true)
- `request_id`: UUID assigned to the API process that handled the request
- `timings`: search, crawl, cleaning, compression, and total pipeline latency
  in milliseconds
- `documents`: a list of `CleanDocument` objects

Each `CleanDocument` preserves the raw crawled fields and adds:

- `cleaned_markdown`
- `original_token_count`
- `cleaned_token_count`
- `tokens_removed`
- `reduction_percentage`
- `cleaning_latency_ms`
- `cleaning_steps_applied`

`timings` includes these fields:

- `search_latency_ms`
- `crawl_latency_ms` (including deterministic ranking when enabled)
- `cleaning_latency_ms`
- `compression_latency_ms` (`0.0` when compression is disabled or an earlier stage fails)
- `total_request_latency_ms` (retrieval-to-compression wall-clock pipeline time)

If a pipeline stage fails, the endpoint returns a successful response with the
effective query, recorded timings, and an empty `documents` list.

The endpoint returns HTTP `429` after 30 requests in 60 seconds, and HTTP `422`
for an invalid request body. Redis must be available for rate limiting.

For the full lifecycle and stage fallback behavior, see the
[request-flow guide](request-flow.md).
