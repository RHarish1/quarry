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
| `compress_output_using_headroom` | `false` | Accepted by the schema; not currently used by the pipeline. |
| `flexible_formatting` | `default_with_metadata` | Accepted by the schema; not currently used by the pipeline. |
| `enhance_query` | `false` | Accepted by the schema; not currently used by the pipeline. |
| `rank_and_score_deterministically` | `false` | Accepted by the schema; not currently used by the pipeline. |
| `time_range` | `null` | One of `day`, `week`, `month`, or `year`. |
| `language` | `null` | Search language. |
| `engines` | `[]` | Search-engine filters. |
| `categories` | `[]` | SearXNG category filters. |
| `format` | `json` | Accepted by the schema; retrieval always requests JSON from SearXNG. |

## Example

```bash
curl -X POST http://localhost:8000/search \
  -H 'content-type: application/json' \
  -d '{"query":"FastAPI lifespan","crawl_websites":true}'
```

## Response Shape

- `query`: the original search query
- `timings`: search, crawl, cleaning, and total request latency in milliseconds
- `documents`: a list of `CleanDocument` objects

Each `CleanDocument` preserves the raw crawled fields and adds:

- `cleaned_markdown`
- `original_token_count`
- `cleaned_token_count`
- `tokens_removed`
- `reduction_percentage`
- `cleaning_latency_ms`
- `cleaning_steps_applied`

If a pipeline stage fails, the endpoint returns a successful response with the
original query, recorded timings, and an empty `documents` list.

For the full lifecycle and stage fallback behavior, see the
[request-flow guide](request-flow.md).
