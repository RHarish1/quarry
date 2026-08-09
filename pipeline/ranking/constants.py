"""Shared constants for the ranking pipeline."""

from __future__ import annotations

# -----------------------------------------------------------------------------
# Candidate Filtering
# -----------------------------------------------------------------------------


BLOCKED_DOMAINS: set[str] = {
    # Social & User-Generated Content
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "www.instagram.com",
    "twitter.com",
    "www.twitter.com",
    "x.com",
    "www.x.com",
    "linkedin.com",
    "www.linkedin.com",
    "tiktok.com",
    "www.tiktok.com",
    "pinterest.com",
    "www.pinterest.com",
    "reddit.com",
    "www.reddit.com",
    "quora.com",
    "www.quora.com",
    "glassdoor.com",
    "www.glassdoor.com",
    # Media, Video & Audio
    "youtube.com",
    "www.youtube.com",
    "vimeo.com",
    "www.vimeo.com",
    "twitch.tv",
    "www.twitch.tv",
    "spotify.com",
    "open.spotify.com",
    "soundcloud.com",
    "www.soundcloud.com",
    "imgur.com",
    "www.imgur.com",
    "flickr.com",
    "www.flickr.com",
    # Search Engines & Directories (Prevents crawling search result pages)
    "google.com",
    "www.google.com",
    "bing.com",
    "www.bing.com",
    "yahoo.com",
    "www.yahoo.com",
    "baidu.com",
    "www.baidu.com",
    "yandex.com",
    "www.yandex.com",
    "duckduckgo.com",
    "www.duckduckgo.com",
    # Known hard-paywalls that trap crawlers
    "bloomberg.com",
    "www.bloomberg.com",
    "wsj.com",
    "www.wsj.com",
}

BLOCKED_PATH_KEYWORDS: set[str] = {
    # Auth & Account
    "/login",
    "/signin",
    "/sign-in",
    "/signup",
    "/sign-up",
    "/register",
    "/account",
    "/auth",
    "/forgot-password",
    "/reset-password",
    "/profile",
    # Legal & Corporate
    "/privacy",
    "/privacy-policy",
    "/cookie",
    "/cookies",
    "/cookie-policy",
    "/terms",
    "/terms-of-service",
    "/tos",
    "/legal",
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/careers",
    "/jobs",
    # Taxonomies & Feeds (Low unique information)
    "/tag/",
    "/tags/",
    "/category/",
    "/categories/",
    "/author/",
    "/authors/",
    "/topic/",
    "/topics/",
    "/feed",
    "/rss",
    "/atom.xml",
    # Interactive & Functional Traps
    "/search",
    "/search-results",
    "/cart",
    "/checkout",
    "/add-to-cart",
    "/basket",  # E-commerce loops
    "/share",
    "/intent/",  # Social sharing links
    "/wp-admin",
    "/wp-login",  # WordPress admin paths
    "?replytocom=",  # WP infinite comment loops
    "/unsubscribe",
}

BLOCKED_FILE_EXTENSIONS: set[str] = {
    # Images
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".bmp",
    ".tiff",
    # Code & Styles
    ".css",
    ".js",
    ".json",
    ".xml",
    ".rss",
    ".atom",
    # Archives & Executables
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".exe",
    ".apk",
    ".dmg",
    ".iso",
    ".bin",
    # Audio & Video
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wav",
    ".ogg",
    ".flac",
    ".webm",
    ".mkv",
    # Fonts
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
    # Documents (Leave these in unless you have specialized parsers like PyPDF2!)
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".epub",
}

# -----------------------------------------------------------------------------
# Quality Filtering
# -----------------------------------------------------------------------------

MIN_QUALITY_SCORE = 0.65

MIN_CHARACTER_COUNT = 300
MIN_WORD_COUNT = 50
MIN_PARAGRAPH_COUNT = 3

# -----------------------------------------------------------------------------
# Recall Strategy
# -----------------------------------------------------------------------------

RECALL_BATCH_SIZE = 5

MAX_RECALL_ATTEMPTS = 5

QUALITY_BUFFER = 2

# Example:
#
# User requests 10 documents
#
# Target = 10
# Internal target = 12
#
# After ranking + cleaning
# Return best 10

# -----------------------------------------------------------------------------
# Ranking
# -----------------------------------------------------------------------------

DEFAULT_TARGET_DOCUMENTS = 10

MAX_CANDIDATES = 100

# -----------------------------------------------------------------------------
# Duplicate Detection
# -----------------------------------------------------------------------------

NORMALIZE_REMOVE_WWW = True

NORMALIZE_REMOVE_TRAILING_SLASH = True

IGNORE_URL_QUERY_PARAMETERS = False

# -----------------------------------------------------------------------------
# Miscellaneous
# -----------------------------------------------------------------------------

HTTP_SCHEMES = {"http", "https"}
