# Caching Stage

Quarry caches completed, non-empty search responses in Redis when a request
sets `enable_caching` to `true`. The cache implementation is in
`pipeline/cache/`.

## Redis Connection

`get_redis()` creates one module-level asynchronous Redis client from
`REDIS_URL`, using `decode_responses=True`. The default URL is
`redis://redis:6379/0`, which targets the Compose Redis service. The API
initializes this client during startup for rate limiting and closes it during
shutdown.

## Cache Keys

Keys have the form `search:<sha256>`. The digest is generated from the request
after:

- removing `enable_caching` and `format`;
- lowercasing and collapsing whitespace in `query`; and
- sorting `engines` and `categories`.

This makes semantically equivalent query spelling and filter order share an
entry. All remaining request fields participate in the key, including fields
that are currently not used by later pipeline stages.

## Reads and Writes

The pipeline checks Redis before retrieval. A hit is deserialized directly into
a `SearchResponse` and bypasses retrieval, crawling, and cleaning. On a miss,
the completed response is stored only if it contains at least one document.

Entries expire after 3,600 seconds (one hour). Redis failures are not handled
inside the cache helper. The route-level exception handler then returns an
empty `SearchResponse` with zero timings rather than an HTTP error.
