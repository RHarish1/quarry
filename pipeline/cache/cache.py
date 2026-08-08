import logging

from models.search import SearchResponse

from .redis import get_redis

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 3600

from pipeline.resilience import (
    REDIS_RETRY,
    CircuitBreaker,
    retry,
)

REDIS_BREAKER = CircuitBreaker(
    name="redis",
    failure_threshold=10,
    recovery_timeout=10,
)


async def get_cache(
    key: str,
) -> SearchResponse | None:
    redis = get_redis()

    async def op():
        return await redis.get(key)

    value = await REDIS_BREAKER.execute(
        lambda: retry(
            op,
            provider="Redis",
            policy=REDIS_RETRY,
        )
    )

    if value is None:
        return None

    return SearchResponse.model_validate_json(value)


async def set_cache(
    key: str,
    response: SearchResponse,
    ttl: int = DEFAULT_TTL_SECONDS,
) -> None:
    redis = get_redis()

    await REDIS_BREAKER.execute(
        lambda: retry(
            lambda: redis.set(
                key,
                response.model_dump_json(),
                ex=ttl,
            ),
            provider="Redis",
            policy=REDIS_RETRY,
        )
    )


async def delete(key: str) -> None:
    redis = get_redis()

    async def op():
        return await redis.get(key)

    await REDIS_BREAKER.execute(
        lambda: retry(
            op,
            provider="Redis",
            policy=REDIS_RETRY,
        )
    )
