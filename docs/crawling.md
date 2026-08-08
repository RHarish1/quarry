# Crawling Stage

The crawling stage converts `SearchResult` objects into raw `Document` objects.
Its public entrypoint is `pipeline/crawler/crawler.py`, while the internal
implementation is split across `pipeline/crawler/fetcher.py`,
`pipeline/crawler/manager.py`, `pipeline/crawler/quality.py`, and
`pipeline/crawler/extractors/`.

## Disabled Crawling

`crawl_websites` defaults to `false`. In this mode no page is fetched: the
search result's snippet becomes `Document.markdown`, `crawl_status` is
`skipped`, and the document metadata records `source: search_provider`.

## Fetch and Extract

When `crawl_websites` is true, Quarry runs a deterministic fetch/extract
pipeline:

1. HTTPX fetches the raw HTML and stores it in an internal `RawDocument`.
2. Trafilatura extracts article content directly from the raw HTML.
3. If the quality score is still low, Playwright renders the page and runs
   Trafilatura again.
4. If the page still does not meet the quality threshold, readability-lxml
   converts the article into Markdown as the final fallback.

The extractor manager evaluates each result with deterministic thresholds for
text length, word count, paragraph count, content-to-HTML ratio, link density,
and navigation ratio. The raw HTML is retained only internally. The downstream
`Document` keeps `html=None` so the API never returns page markup.

The public `Document` preserves the final URL, content type, timing
information, and safe extraction metadata needed by the cleaning stage. Its
`crawl_status` is the extractor method that produced the result
(`trafilatura`, `playwright_trafilatura`, or `readability`). The raw response
HTML and HTTP status are kept only in the internal `RawDocument`; API responses
set `html` to `null`.

All external fetching uses a shared asynchronous HTTPX client created during
application startup. It follows redirects, sends `QuarryBot/0.3` as the default
user agent, uses a 30-second default HTTP timeout, and permits up to 100 open
connections (20 keep-alive connections).

### Ranked crawling and robots.txt

Robots checks happen only for ranked crawling—when both `crawl_websites` and
`rank_and_score_deterministically` are true. Quarry fetches and caches each
origin's `robots.txt`, then removes URLs the configured user agent cannot fetch.
A missing `robots.txt` permits crawling; an error retrieving or parsing it
causes Quarry to skip that origin conservatively. Candidate filtering then
removes duplicate, blocked, and clearly non-content URLs before crawling starts.

## Failure Handling

A timeout, HTTP client error, render failure, or extraction failure produces a
fallback document rather than dropping the search result. Fallbacks preserve
the search URL, title, and snippet, set a status of `fetch_failed` or
`extract_failed`, and record a `crawl_fallback_reason` in metadata.
