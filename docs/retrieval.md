# Retrieval Stage

The retrieval stage turns a `SearchRequest` into normalized `SearchResult`
objects. Its implementation is in `pipeline/retrieval/searxng.py`.

## Request to SearXNG

Quarry sends a form-encoded `POST` request to `/search` on
`SEARXNG_BASE_URL`. It always requests `format=json` and sends these request
fields when supplied:

| Quarry field | SearXNG parameter |
| --- | --- |
| `query` | `q` |
| `categories` | `categories`, comma-separated |
| `language` | `language` |
| `time_range` | `time_range` |
| `engines` | `engines`, comma-separated |

Requests use the startup-created shared HTTP client. Its default timeout is 30
seconds, while `SEARXNG_TIMEOUT_SECONDS` remains the configured retrieval
timeout setting. The client follows redirects and sends the configured
`QuarryBot/0.3` user agent.

## Normalization

Each item in SearXNG's `results` array becomes a `SearchResult` with `url`,
`title`, and `content`. Every other upstream field is preserved in `metadata`.
Malformed items are skipped, and a payload without a list-valued `results`
field produces an empty result list.

Connection failures, timeouts, non-success upstream responses, and non-JSON
payloads are represented as HTTP 502 errors inside the retrieval client. Calls
are wrapped in the SearXNG retry policy (up to three retries after the initial
attempt for configured transient failures) and a circuit breaker that opens
after five failures for 20 seconds. The top-level pipeline catches a final
failure and returns an empty response with the measured search latency instead
of propagating it to the API caller.
