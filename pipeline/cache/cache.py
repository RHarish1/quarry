from .redis import get_redis
from models.search import SearchResponse


DEFAULT_TTL_SECONDS = 3600


async def get(
    key: str,
) -> SearchResponse | None:
    redis = get_redis()

    value = await redis.get(key)

    if value is None:
        return None

    return SearchResponse.model_validate_json(value)


async def set(
    key: str,
    response: SearchResponse,
    ttl: int = DEFAULT_TTL_SECONDS,
) -> None:
    redis = get_redis()

    await redis.set(
        key,
        response.model_dump_json(),
        ex=ttl,
    )


async def delete(key: str) -> None:
    redis = get_redis()

    await redis.delete(key)