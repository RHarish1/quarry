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

The public `Document` preserves the final URL, HTTP status, content type,
timing information, and safe metadata needed by the cleaning stage.

## Failure Handling

A timeout, HTTP client error, render failure, or extraction failure produces a
fallback document rather than dropping the search result. Fallbacks preserve
the search URL, title, and snippet, set a status of `fetch_failed` or
`extract_failed`, and record a `crawl_fallback_reason` in metadata.