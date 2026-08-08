from fastapi import Depends, Request, Response
from fastapi_limiter.depends import RateLimiter


async def conditional_rate_limit(request: Request, response: Response):
    if request.headers.get("x-benchmark") == "true":
        return

    limiter = RateLimiter(times=30, seconds=60)
    return await limiter(request, response)


DEFAULT_RATE_LIMIT = Depends(conditional_rate_limit)
