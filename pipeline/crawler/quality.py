"""Deterministic extraction quality scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lxml import html as lxml_html
from lxml.etree import ParserError

from models.document import Document
from pipeline.crawler.types import ExtractedDocument, RawDocument

WORD_PATTERN = re.compile(r"\w+|[^\w\s]")
BLANK_BLOCK_PATTERN = re.compile(r"\n\s*\n")


@dataclass(frozen=True, slots=True)
class ExtractionQualityThresholds:
    """Configurable quality thresholds for content extraction."""

    minimum_character_count: int = 600
    minimum_word_count: int = 90
    minimum_paragraph_count: int = 3
    minimum_content_html_ratio: float = 0.08
    maximum_link_density: float = 0.30
    maximum_navigation_ratio: float = 0.35
    minimum_score: float = 0.68
    character_target: int = 1800
    word_target: int = 260
    paragraph_target: int = 8
    content_html_ratio_target: float = 0.20
    link_density_target: float = 0.12
    navigation_ratio_target: float = 0.12
    weight_title: float = 0.12
    weight_characters: float = 0.18
    weight_words: float = 0.16
    weight_paragraphs: float = 0.14
    weight_content_ratio: float = 0.16
    weight_link_density: float = 0.12
    weight_navigation_ratio: float = 0.12


@dataclass(frozen=True, slots=True)
class ExtractionQuality:
    """Deterministic signal bundle for an extractor result."""

    character_count: int
    word_count: int
    paragraph_count: int
    content_html_ratio: float
    link_density: float
    navigation_ratio: float
    title_present: bool
    score: float
    accepted: bool
    reasons: tuple[str, ...] = ()


def _count_words(text: str) -> int:
    return len(WORD_PATTERN.findall(text))


def _count_paragraphs(markdown: str) -> int:
    return sum(1 for block in BLANK_BLOCK_PATTERN.split(markdown) if block.strip())


def _safe_html_root(raw_html: str):
    try:
        return lxml_html.fromstring(raw_html)
    except ParserError:
        return None


def _ratio(total: int, part: int) -> float:
    return part / total if total > 0 else 0.0


def _bounded_quality(value: float, target: float) -> float:
    if target <= 0:
        return 1.0

    return max(0.0, min(value / target, 1.0))


def filter_quality(
    documents: list[Document],
    minimum_score: float,
) -> list[Document]:
    return [
        document
        for document in documents
        if document.metadata.get("quality_score", 0.0) >= minimum_score
    ]


def sort_quality(
    documents: list[Document],
) -> list[Document]:
    return sorted(
        documents,
        key=lambda document: document.metadata.get("quality_score", 0.0),
        reverse=True,
    )


def score_extraction(
    raw_document: RawDocument,
    extracted_document: ExtractedDocument,
    thresholds: ExtractionQualityThresholds,
) -> ExtractionQuality:
    """Score an extracted document using deterministic heuristics."""

    character_count = len(extracted_document.plain_text.strip())
    word_count = _count_words(extracted_document.plain_text)
    paragraph_count = _count_paragraphs(extracted_document.markdown)
    content_html_ratio = _ratio(raw_document.html_size, character_count)

    root = _safe_html_root(raw_document.raw_html)
    if root is None:
        link_density = 0.0
        navigation_ratio = 0.0
    else:
        total_text = len(" ".join(root.xpath(".//text()[normalize-space()]")).strip())
        link_text = len(" ".join(root.xpath(".//a//text()[normalize-space()]")).strip())
        nav_text = len(
            " ".join(
                root.xpath(
                    ".//nav//text()[normalize-space()] | .//header//text()[normalize-space()] | .//footer//text()[normalize-space()] | .//aside//text()[normalize-space()]"
                )
            ).strip()
        )
        link_density = _ratio(total_text, link_text)
        navigation_ratio = _ratio(total_text, nav_text)

    title_present = bool(extracted_document.title.strip())

    if character_count < thresholds.minimum_character_count:
        reasons = ("minimum_character_count",)
    elif word_count < thresholds.minimum_word_count:
        reasons = ("minimum_word_count",)
    elif paragraph_count < thresholds.minimum_paragraph_count:
        reasons = ("minimum_paragraph_count",)
    else:
        reasons = ()

    score = (
        (1.0 if title_present else 0.0) * thresholds.weight_title
        + _bounded_quality(character_count, thresholds.character_target)
        * thresholds.weight_characters
        + _bounded_quality(word_count, thresholds.word_target) * thresholds.weight_words
        + _bounded_quality(paragraph_count, thresholds.paragraph_target)
        * thresholds.weight_paragraphs
        + _bounded_quality(content_html_ratio, thresholds.content_html_ratio_target)
        * thresholds.weight_content_ratio
        + (1.0 - _bounded_quality(link_density, thresholds.link_density_target))
        * thresholds.weight_link_density
        + (1.0 - _bounded_quality(navigation_ratio, thresholds.navigation_ratio_target))
        * thresholds.weight_navigation_ratio
    )

    accepted = (
        title_present
        and character_count >= thresholds.minimum_character_count
        and word_count >= thresholds.minimum_word_count
        and paragraph_count >= thresholds.minimum_paragraph_count
        and content_html_ratio >= thresholds.minimum_content_html_ratio
        and link_density <= thresholds.maximum_link_density
        and navigation_ratio <= thresholds.maximum_navigation_ratio
        and score >= thresholds.minimum_score
    )

    return ExtractionQuality(
        character_count=character_count,
        word_count=word_count,
        paragraph_count=paragraph_count,
        content_html_ratio=content_html_ratio,
        link_density=link_density,
        navigation_ratio=navigation_ratio,
        title_present=title_present,
        score=score,
        accepted=accepted,
        reasons=reasons,
    )
