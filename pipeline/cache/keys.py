import hashlib
import json

from models.search import SearchRequest


def make_cache_key(request: SearchRequest) -> str:
    payload = request.model_dump()

    # Doesn't affect search output
    payload.pop("enable_caching", None)
    payload.pop("format", None)

    # Normalize query
    payload["query"] = " ".join(payload["query"].lower().split())

    # Order-independent fields
    payload["engines"] = sorted(payload["engines"])
    payload["categories"] = sorted(payload["categories"])

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return f"search:{digest}"
