# Search API

`POST /search` accepts a `SearchRequest` body and returns a `SearchResponse` object.

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
