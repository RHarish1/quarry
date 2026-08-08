import asyncio
import json
import time
from random import uniform
from statistics import mean

import httpx

API_URL = "http://localhost:8000/search"

QUERY_FILES = {
    "easy": "tests/datasets/easy_queries.txt",
    "medium": "tests/datasets/medium_queries.txt",
    "hard": "tests/datasets/hard_queries.txt",
}

CONFIGS = [
    {
        "name": "baseline",
        "enable_caching": False,
        "crawl_websites": True,
        "rank_and_score_deterministically": True,
        "compress_output": False,
    },
    {
        "name": "cache_on",
        "enable_caching": True,
        "crawl_websites": True,
        "rank_and_score_deterministically": True,
        "enhance_query": True,
        "compress_output": False,
    },
    {
        "name": "compression_1048_cache_off",
        "enable_caching": False,
        "crawl_websites": True,
        "rank_and_score_deterministically": True,
        "compress_output": True,
        "target_token_budget": 1048,
    },
]


def load_queries(path: str):
    with open(path) as f:
        return [q.strip() for q in f if q.strip()]


async def run_single(client, query, config, mode="benchmark"):
    payload = {
        "query": query,
        "cleaning_level": 1,
        "target_documents": 5,
        **config,
    }

    t0 = time.perf_counter()

    try:

        res = await client.post(
            API_URL,
            json=payload,
            headers={"x-mode": mode},
        )
        res.raise_for_status()
        data = res.json()
        total_ms = (time.perf_counter() - t0) * 1000

        return {
            "success": data.get("success", False),
            "latency_ms": total_ms,
            "benchmark": data.get("benchmark"),
        }

    except Exception as e:  # noqa: BLE001
        print(e)
        return {
            "success": False,
            "latency_ms": (time.perf_counter() - t0) * 1000,
            "error": str(e),
            "benchmark": None,
        }


def percentile(arr, p):
    if not arr:
        return 0
    arr = sorted(arr)
    k = int(len(arr) * p)
    return arr[min(k, len(arr) - 1)]


def summarize(results):
    latencies: list[int] = [r["latency_ms"] for r in results if r["success"]]

    benchmarks = [r["benchmark"] for r in results if r["benchmark"]]

    cache_hits = sum(1 for b in benchmarks if b and b.get("cache_hit"))

    tokens_before = []
    tokens_after = []

    for b in benchmarks:
        if not b:
            continue
        if b.get("tokens_before", 0) > 0:
            tokens_before.append(b["tokens_before"])
            tokens_after.append(b["tokens_after"])

    return {
        "requests": len(results),
        "success_rate": sum(r["success"] for r in results) / len(results),
        "avg_latency": mean(latencies) if latencies else 0,
        "p50": percentile(latencies, 0.50),
        "p95": percentile(latencies, 0.95),
        "p99": percentile(latencies, 0.99),
        "cache_hit_rate": cache_hits / len(benchmarks) if benchmarks else 0,
        "avg_token_reduction": (
            mean((b - a) / b for b, a in zip(tokens_before, tokens_after) if b > 0)
            if tokens_before
            else 0
        ),
    }


async def run_benchmark():
    async with httpx.AsyncClient(timeout=30) as client:
        for difficulty, file_path in QUERY_FILES.items():
            queries = load_queries(file_path)

            for config in CONFIGS:
                print(f"\n=== {difficulty.upper()} | {config['name']} ===")
                SEMAPHORE = asyncio.Semaphore(2)
                if config.get("enable_caching"):
                    print("Warming cache...")
                    for query in queries:
                        await run_single(client, query, config)

                async def run_limited(client, query, config, seamphore=SEMAPHORE):
                    async with seamphore:
                        await asyncio.sleep(0.3 + uniform(0, 0.2))
                        return await run_single(client, query, config)

                await asyncio.sleep(1)
                tasks = [run_limited(client, query, config) for query in queries]

                results = await asyncio.gather(*tasks)

                summary = summarize(results)

                print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(run_benchmark())
