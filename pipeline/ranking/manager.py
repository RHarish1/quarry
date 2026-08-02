"""Ranking pipeline orchestration."""

from __future__ import annotations

from models.document import Documents
from models.search import CrawlRequest, SearchResults
from pipeline.crawler.crawler import crawl_documents
from pipeline.crawler.quality import filter_quality as filter_documents_by_quality
from pipeline.retrieval.robots import can_crawl

from .constants import MIN_QUALITY_SCORE
from .filters import filter_candidates
from .recall import needs_recall, select_recall_candidates


async def rank_documents(
    search_results: SearchResults,
    *,
    target_documents: int,
    crawl_request: CrawlRequest,
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

    accepted_documents = []
    current_index = 0

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

        crawled_documents = await crawl_documents(batch_request)

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

    return Documents(documents=accepted_documents[:target_documents])
