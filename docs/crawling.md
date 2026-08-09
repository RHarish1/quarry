# Crawling Stage

The crawling stage converts `SearchResult` objects into raw `Document` objects.
Entry point: `pipeline/crawler/crawler.py`. Internal implementation is split
across `fetcher.py`, `manager.py`, `quality.py`, and `extractors/`.

## Disabled Crawling (`crawl_websites=false`)

No page is fetched. Each search snippet becomes a `Document` with:

- `markdown` = snippet text from the search provider
- `crawl_status` = `"skipped"`
- `metadata.source` = `"search_provider"`

## Fetch and Extract (`crawl_websites=true`)

A `asyncio.Semaphore` (size = `CRAWL_MAX_CONCURRENCY`) bounds concurrent
fetches. Each URL is processed by `_crawl_search_result`:

1. **Fetch** — `fetcher.py` uses the shared HTTPX client to download the raw
   HTML. Stores response in an internal `RawDocument` (never exposed in the API
   response — `Document.html` is always `null`).
2. **Extract** — `ExtractorManager.extract()` runs the waterfall below.
3. **Fallback** — any exception produces a `Document` with `crawl_status`
   `"fetch_failed"` or `"extract_failed"` and the original snippet as content.

### Extractor Waterfall

`ExtractorManager` tries extractors in order and stops at the first one whose
quality score meets the acceptance threshold (`minimum_score = 0.68`):

| Priority | Extractor | Method |
| --- | --- | --- |
| 1 | `TrafilaturaExtractor` | Article extraction directly on raw HTML |
| 2 | `PlaywrightTrafilaturaExtractor` | JS-render the page, then Trafilatura |
| 3 | `ReadabilityExtractor` | readability-lxml → Markdownify |

If no extractor passes the threshold, the **highest-scoring** result is used
rather than discarding the document.

### Deterministic Quality Score (`pipeline/crawler/quality.py`)

Each extractor result is scored across 7 weighted signals:

| Signal | Weight | Target value |
| --- | ---: | --- |
| Title present | 0.12 | Boolean |
| Character count | 0.18 | 1800 chars |
| Word count | 0.16 | 260 words |
| Paragraph count | 0.14 | 8 paragraphs |
| Content / HTML ratio | 0.16 | 0.20 |
| Link density (lower = better) | 0.12 | 0.12 |
| Navigation ratio (lower = better) | 0.12 | 0.12 |

A result is **accepted** when all of these hard thresholds are met:

| Threshold | Value |
| --- | --- |
| Minimum characters | 600 |
| Minimum words | 90 |
| Minimum paragraphs | 3 |
| Minimum content/HTML ratio | 0.08 |
| Maximum link density | 0.30 |
| Maximum navigation ratio | 0.35 |
| Minimum score | 0.68 |

## Ranked Crawling (`crawl_websites=true`, `rank_and_score_deterministically=true`)

Implemented in `pipeline/ranking/manager.py` using `asyncio.Queue`.

### Pre-crawl steps

1. **robots.txt check** — `pipeline/retrieval/robots.py` fetches and caches
   each origin's `robots.txt` for `QuarryBot/0.6`. Missing files allow crawling;
   fetch errors cause a conservative skip.
2. **Candidate filtering** — `pipeline/ranking/filters.py` removes:
   - Non-HTTP/HTTPS URLs
   - Duplicate normalised URLs
   - Configured blocked domains
   - Static file extensions (`.pdf`, `.zip`, images, …)
   - Noise paths: `/login`, `/privacy`, `/cookie`, `/terms`, `/feed`, `/tag`, `/category`

### Queue-based worker loop

```
task_queue  ◄── all candidates loaded at startup
result_queue ◄── workers push completed Documents

Orchestrator loop:
  while accepted < target_documents AND processed < total:
      doc = await result_queue.get()   # fastest-completed, not batch-wait
      if quality_score(doc) ≥ MIN_QUALITY_SCORE:
          accepted.append(doc)
      if len(accepted) >= target_documents:
          break   # cancel remaining workers immediately
```

`N = min(CRAWL_MAX_CONCURRENCY, total_candidates)` workers run concurrently.
Workers are cancelled the moment the target is met, releasing resources early.

Final output: accepted documents sorted by `quality_score` descending, capped
at `target_documents`.

### Conditional behaviour summary

| `crawl_websites` | `rank_and_score_deterministically` | Behaviour |
| --- | --- | --- |
| `false` | any | Snippets only; `crawl_status: "skipped"` |
| `true` | `false` | Fetch all results concurrently via semaphore |
| `true` | `true` | robots.txt → filter → queue-based workers → quality gate → stop at target |

## Failure Handling

| Failure type | Result |
| --- | --- |
| Fetch exception | `crawl_status: "fetch_failed"`, snippet retained as content |
| Extraction exception | `crawl_status: "extract_failed"`, snippet retained as content |
| All extractors below threshold | Highest-scoring extractor result used |
| robots.txt fetch error | Origin skipped conservatively |
| Worker crash in ranked mode | `None` pushed to result queue; orchestrator skips it |
