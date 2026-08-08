from prometheus_client import Counter, Histogram

# Cache Metrics
SEARCH_CACHE_HITS = Counter(
    "quarry_search_cache_hits_total", 
    "Total search requests served from cache"
)
CACHE_LOOKUP_MS = Histogram(
    "quarry_cache_lookup_ms", 
    "Time spent checking the cache (ms)"
)

# Search & Crawl Metrics
URLS_FOUND = Counter(
    "quarry_urls_found_total", 
    "Total candidate URLs returned by the search provider"
)
PAGES_CRAWLED = Counter(
    "quarry_pages_crawled_total", 
    "Total pages successfully crawled"
)
CRAWL_FAILURES = Counter(
    "quarry_crawl_failures_total", 
    "Total pages that failed to crawl"
)

# Compression Metrics
COMPRESSION_RATIO = Histogram(
    "quarry_compression_ratio", 
    "Distribution of document compression ratios"
)
TOKENS_SAVED = Counter(
    "quarry_tokens_saved_total", 
    "Total tokens removed via compression"
)