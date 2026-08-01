"""Shared constants for the ranking pipeline."""

from __future__ import annotations

# -----------------------------------------------------------------------------
# Candidate Filtering
# -----------------------------------------------------------------------------


BLOCKED_DOMAINS = {
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
}

BLOCKED_PATH_KEYWORDS: set[str] = {
    "/login",
    "/signin",
    "/sign-in",
    "/signup",
    "/register",
    "/account",
    "/auth",
    "/privacy",
    "/privacy-policy",
    "/cookie",
    "/cookies",
    "/terms",
    "/terms-of-service",
    "/contact",
    "/about",
    "/careers",
    "/jobs",
    "/tag/",
    "/tags/",
    "/category/",
    "/categories/",
    "/author/",
    "/authors/",
    "/feed",
    "/rss",
    "/search",
}

BLOCKED_FILE_EXTENSIONS: set[str] = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".css",
    ".js",
    ".xml",
    ".zip",
    ".rar",
    ".exe",
    ".apk",
    ".dmg",
    ".iso",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
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
