"""Extractor orchestration for Quarry."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from pipeline.crawler.extractors import PlaywrightTrafilaturaExtractor, ReadabilityExtractor, TrafilaturaExtractor
from pipeline.crawler.extractors.base import BaseExtractor
from pipeline.crawler.quality import ExtractionQuality, ExtractionQualityThresholds, score_extraction
from pipeline.crawler.types import ExtractedDocument, RawDocument

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ExtractorManager:
    """Try deterministic extractors in order until the quality threshold is met."""

    thresholds: ExtractionQualityThresholds = field(default_factory=ExtractionQualityThresholds)
    extractors: list[BaseExtractor] = field(
        default_factory=lambda: [
            TrafilaturaExtractor(),
            PlaywrightTrafilaturaExtractor(),
            ReadabilityExtractor(),
        ]
    )

    async def extract(self, raw_document: RawDocument) -> ExtractedDocument:
        best_document: ExtractedDocument | None = None
        best_quality: ExtractionQuality | None = None
        current_html: str | None = raw_document.raw_html

        for extractor in self.extractors:
            logger.info(
                "crawler.extractor_attempt",
                extra={"extractor": extractor.name, "url": raw_document.final_url},
            )
            extracted_document = await extractor.extract(raw_document, current_html)
            quality = score_extraction(raw_document, extracted_document, self.thresholds)
            extracted_document.extraction_confidence = quality.score

            logger.info(
                "crawler.extractor_result",
                extra={
                    "extractor": extractor.name,
                    "url": raw_document.final_url,
                    "accepted": quality.accepted,
                    "score": round(quality.score, 4),
                    "character_count": quality.character_count,
                    "word_count": quality.word_count,
                    "paragraph_count": quality.paragraph_count,
                    "link_density": round(quality.link_density, 4),
                    "navigation_ratio": round(quality.navigation_ratio, 4),
                },
            )

            if best_quality is None or quality.score > best_quality.score:
                best_document = extracted_document
                best_quality = quality

            if quality.accepted:
                return extracted_document

            current_html = extracted_document.source_html or current_html

        if best_document is None:
            return ExtractedDocument(
                title="",
                markdown="",
                plain_text="",
                metadata={"source": "extractor_manager_empty"},
                extraction_method="extractor_manager_empty",
                extraction_confidence=0.0,
                extraction_duration_ms=0.0,
                extracted_text_size=0,
                extracted_markdown_size=0,
                source_html=None,
            )

        return best_document