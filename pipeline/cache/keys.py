import hashlib
import json

from models.search import SearchRequest


def make_cache_key(request: SearchRequest) -> str:
    payload = request.model_dump()
    payload.setdefault("compress_output", False)
    payload.setdefault("crawl_websites", False)
    payload.setdefault("rank_and_score_deterministically", False)
    payload.setdefault("enhance_query", False)
    payload.setdefault("cleaning_level", 0)

    # Doesn't affect search output
    payload.pop("enable_caching", None)
    if not payload.get("compress_output"):
        payload.pop("target_token_budget", None)

    # Order-independent fields
    payload["engines"] = sorted(payload["engines"])
    payload["categories"] = sorted(payload["categories"])

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    print("CACHE_KEY_PAYLOAD:", canonical)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return f"search:{digest}"
