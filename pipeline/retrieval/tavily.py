import os

import httpx

from models.search import SearchResult, SearchResults

TAVILY_API_URL = "https://api.tavily.com/search"


async def search_tavily(query: str, max_results: int = 10) -> SearchResults:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return SearchResults()

    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(TAVILY_API_URL, json=payload)

    if resp.status_code != 200:
        return SearchResults()

    data = resp.json()
    results = []

    for r in data.get("results", []):
        results.append(
            SearchResult(
                url=r.get("url", ""),
                title=r.get("title", ""),
                content=r.get("content", ""),
                metadata={
                    "source": "tavily",
                    "score": r.get("score"),
                },
            )
        )

    return SearchResults(results=results)
