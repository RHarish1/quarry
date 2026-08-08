import os

import httpx

from models.search import SearchResult, SearchResults

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"


async def search_brave(query: str, count: int = 10) -> SearchResults:
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        return SearchResults()

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    }

    params = {
        "q": query,
        "count": count,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(BRAVE_API_URL, headers=headers, params=params)

    if resp.status_code != 200:
        return SearchResults()

    data = resp.json()
    results = []

    for r in data.get("web", {}).get("results", []):
        results.append(
            SearchResult(
                url=r.get("url", ""),
                title=r.get("title", ""),
                content=r.get("description", ""),
                metadata={
                    "source": "brave",
                    "age": r.get("age"),
                    "language": r.get("language"),
                },
            )
        )

    return SearchResults(results=results)
