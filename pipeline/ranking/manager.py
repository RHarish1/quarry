"""Ranking pipeline orchestration."""

from __future__ import annotations

import asyncio

from typing_extensions import deprecated

from models.document import Document, Documents
from models.search import CrawlRequest, SearchBenchmark, SearchResult, SearchResults
from pipeline.crawler.crawler import crawl_documents
from pipeline.crawler.quality import filter_quality as filter_documents_by_quality
from pipeline.retrieval.robots import can_crawl

from .constants import MIN_QUALITY_SCORE
from .filters import filter_candidates
from .recall import needs_recall, select_recall_candidates


async def crawl_and_rank_documents(
    search_results: SearchResults,
    *,
    target_documents: int,
    crawl_request: CrawlRequest,
    benchmark: SearchBenchmark | None = None,
    mode: str = "production",
) -> Documents:
    """
    Produce a fixed number of high-quality documents using an async queue.
    """
    allowed_websites = await can_crawl(search_results.results)
    candidates = filter_candidates(allowed_websites.results)

    if benchmark:
        benchmark.urls_filtered_out = len(candidates)
        benchmark.crawlable_urls = len(allowed_websites.results)

    accepted_documents = []
    processed_count = 0
    total_candidates = len(candidates)

    # 1. Setup Queues
    task_queue: asyncio.Queue[SearchResult] = asyncio.Queue()
    result_queue: asyncio.Queue[Document | None] = asyncio.Queue()

    # Load all candidates into the task queue
    for candidate in candidates:
        task_queue.put_nowait(candidate)

    # 2. Define the Worker
    async def worker():
        while True:
            try:
                # Grab the next URL from the queue
                candidate = await task_queue.get()

                # Wrap it in a single-item request to use your existing crawler logic
                single_request = crawl_request.model_copy(
                    update={"search_results": SearchResults(results=[candidate])}
                )

                # Fetch and extract
                crawled_docs = await crawl_documents(single_request, mode)

                # Push the finished document to the results queue
                doc = crawled_docs.documents[0] if crawled_docs.documents else None
                await result_queue.put(doc)

                task_queue.task_done()
            except asyncio.CancelledError:
                break  # Graceful exit when orchestrator cancels workers
            except Exception:  # noqa
                # Ensure we don't dead-lock the orchestrator if a worker crashes
                await result_queue.put(None)
                task_queue.task_done()

    # 3. Spin up Workers (bounded by max_concurrency)
    concurrency_limit = min(crawl_request.max_concurrency, total_candidates)
    workers = [asyncio.create_task(worker()) for _ in range(concurrency_limit)]

    # 4. Orchestrator Loop: Process results as they stream in
    try:
        while (
            len(accepted_documents) < target_documents
            and processed_count < total_candidates
        ):
            # This awaits the FASTEST completed document, no batch waiting!
            doc = await result_queue.get()
            processed_count += 1

            if doc:
                # Dynamic scoring
                score = float(doc.metadata.get("quality_score", 0.0))
                if score <= 0.0:
                    score = float(doc.metadata.get("extraction_confidence", 0.0))
                doc.metadata["quality_score"] = score

                # Quality filtering
                filtered = filter_documents_by_quality([doc], MIN_QUALITY_SCORE)
                if filtered:
                    accepted_documents.extend(filtered)

            # Check if we should abort early
            if len(accepted_documents) >= target_documents:
                break

    finally:
        # 5. Cleanup: The moment we hit our target, cancel all active background workers
        for w in workers:
            w.cancel()
        # Await them to ensure they shut down cleanly and release resources
        await asyncio.gather(*workers, return_exceptions=True)

    # 6. Final Sorting & Benchmarks
    accepted_documents.sort(
        key=lambda document: document.metadata.get("quality_score", 0.0),
        reverse=True,
    )

    if benchmark:
        benchmark.pages_successfully_crawled = target_documents
        # Failures = Total URLs we attempted - successful docs we accepted
        benchmark.crawl_failures = processed_count - len(accepted_documents)

    return Documents(documents=accepted_documents[:target_documents])


@deprecated("Use crawl_and_rank_documents() instead.")
async def sync_crawl_and_rank_documents(
    search_results: SearchResults,
    *,
    target_documents: int,
    crawl_request: CrawlRequest,
    benchmark: SearchBenchmark | None = None,
    mode: str = "production",
) -> Documents:
    """
    Produce a fixed number of high-quality documents.

    Pipeline:
        Search Results
            ↓
        URL Filtering
            ↓
        Crawl + Extraction
            ↓
        Quality Scoring
            ↓
        Quality Filtering
            ↓
        Recall (if required)
            ↓
        Return top documents
    """
    allowed_websites = await can_crawl(search_results.results)
    candidates = filter_candidates(allowed_websites.results)
    if benchmark:
        benchmark.urls_filtered_out = len(candidates)
        benchmark.crawlable_urls = len(allowed_websites.results)

    accepted_documents = []
    current_index = 0
    # average_crawl_depth will be calculated once queue based crawling is implemented
    while len(accepted_documents) < target_documents:
        batch = select_recall_candidates(
            candidates,
            start=current_index,
            count=crawl_request.max_concurrency,
        )

        if not batch:
            break

        current_index += len(batch)

        batch_request = crawl_request.model_copy(
            update={"search_results": SearchResults(results=batch)}
        )

        crawled_documents = await crawl_documents(batch_request, mode)

        for document in crawled_documents.documents:
            score = float(document.metadata.get("quality_score", 0.0))
            if score <= 0.0:
                score = float(document.metadata.get("extraction_confidence", 0.0))
            document.metadata["quality_score"] = score

        accepted_documents.extend(
            filter_documents_by_quality(crawled_documents.documents, MIN_QUALITY_SCORE)
        )

        if not needs_recall(
            accepted=len(accepted_documents),
            requested=target_documents,
            remaining=len(candidates) - current_index,
        ):
            break

    accepted_documents.sort(
        key=lambda document: document.metadata.get("quality_score", 0.0),
        reverse=True,
    )
    if benchmark:
        benchmark.pages_successfully_crawled = target_documents
        benchmark.crawl_failures = current_index - target_documents + 1
    return Documents(documents=accepted_documents[:target_documents])
