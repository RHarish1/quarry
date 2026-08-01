# Compression Stage

Compression is an optional deterministic stage that runs after cleaning. It is
implemented in `pipeline/compression/compressor.py`.

## Enabling Compression

Set `compress_output` to `true` in a `POST /search` request. Use
`target_token_budget` to set a positive per-document limit; when omitted,
Quarry uses 2,048 estimated tokens per document.

```json
{
  "query": "FastAPI lifecycle",
  "crawl_websites": true,
  "compress_output": true,
  "target_token_budget": 1024
}
```

## Behavior

For every `CleanDocument`, the compressor:

1. Splits `cleaned_markdown` into paragraphs.
2. Removes duplicate paragraphs case-insensitively.
3. Removes short or boilerplate paragraphs containing cookie, privacy-policy,
   consent, or advertisement language.
4. Keeps complete paragraphs until the token budget would be exceeded.
5. Updates the cleaned Markdown, token/reduction metrics, and appends
   `deterministic_compression` to `cleaning_steps_applied`.

The compressor estimates tokens as four characters per token. This is a
deterministic approximation, not a model-specific tokenizer.

## Timing and Failure Behavior

`SearchResponse.timings.compression_latency_ms` records the elapsed compression
time. It is `0.0` when compression is disabled or an earlier stage fails. The
total pipeline latency is recorded only after compression completes.

If compression raises an exception, Quarry logs the error, returns the cleaned
documents unchanged, and still reports the elapsed failed-attempt latency.
