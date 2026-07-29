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

The upstream timeout is configured with `SEARXNG_TIMEOUT_SECONDS` (20 seconds
by default).

## Normalization

Each item in SearXNG's `results` array becomes a `SearchResult` with `url`,
`title`, and `content`. Every other upstream field is preserved in `metadata`.
Malformed items are skipped, and a payload without a list-valued `results`
field produces an empty result list.

Connection failures, timeouts, non-success upstream responses, and non-JSON
payloads are represented as HTTP 502 errors inside the retrieval client. The
top-level pipeline catches stage failures and returns an empty response instead
of propagating them to the API caller.
