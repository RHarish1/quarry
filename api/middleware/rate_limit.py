from fastapi import Depends
from fastapi_limiter.depends import RateLimiter

DEFAULT_RATE_LIMIT = Depends(
    RateLimiter(times=30, seconds=60)
)
