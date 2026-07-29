# Crawling Stage

The crawling stage converts `SearchResult` objects into raw `Document` objects.
Its implementation is in `pipeline/crawler/crawler.py`.

## Disabled Crawling

`crawl_websites` defaults to `false`. In this mode no page is fetched: the
search result's snippet becomes `Document.markdown`, `crawl_status` is
`skipped`, and the document metadata records `source: search_provider`.

## Fetching Pages

When `crawl_websites` is true, Quarry fetches each result URL with HTTPX. It
follows redirects, uses the `Quarry/1.0` user agent, and limits simultaneous
fetches with `CRAWL_MAX_CONCURRENCY` (default: 4). Each fetch has the
`CRAWL_TIMEOUT_SECONDS` timeout (default: 30 seconds).

For successful responses, the stage:

1. Removes noisy HTML elements such as scripts, styles, SVGs, iframes, and forms.
2. Converts the page body, `main`, or `article` content to ATX-style Markdown.
3. Normalizes the Markdown and falls back to the search snippet if it is empty.
4. Extracts the page title, canonical URL, final redirected URL, content type,
   timestamp, and elapsed crawl time.

The original HTML is retained in `Document.html`; the fetched content is marked
with `source: fetched_html` in metadata.

## Failure Handling

A timeout, HTTP client error, unexpected crawler failure, or HTTP status of 400
or higher produces a fallback document rather than dropping the search result.
Fallbacks preserve the search URL, title, and snippet, set a status of
`timeout`, `crawl_failed`, or `http_error`, and record a
`crawl_fallback_reason` in metadata.
