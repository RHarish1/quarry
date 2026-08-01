"""Extractor implementations for Quarry."""

from pipeline.crawler.extractors.base import BaseExtractor as BaseExtractor
from pipeline.crawler.extractors.playwright import (
    PlaywrightTrafilaturaExtractor as PlaywrightTrafilaturaExtractor,
)
from pipeline.crawler.extractors.readability import (
    ReadabilityExtractor as ReadabilityExtractor,
)
from pipeline.crawler.extractors.trafilatura import (
    TrafilaturaExtractor as TrafilaturaExtractor,
)
