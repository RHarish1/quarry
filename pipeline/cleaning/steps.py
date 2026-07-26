"""Deterministic markdown cleaning steps for Quarry."""

from __future__ import annotations

import re

CODE_FENCE_PATTERN = re.compile(r"```.*?```", re.DOTALL)
BLANK_LINE_PATTERN = re.compile(r"\n{3,}")
WHITESPACE_PATTERN = re.compile(r"[ \t]+")
HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+)$")


def _split_code_fences(markdown: str) -> list[tuple[bool, str]]:
    """Split markdown into code and non-code segments."""

    segments: list[tuple[bool, str]] = []
    cursor = 0
    for match in CODE_FENCE_PATTERN.finditer(markdown):
        if match.start() > cursor:
            segments.append((False, markdown[cursor:match.start()]))
        segments.append((True, match.group(0)))
        cursor = match.end()

    if cursor < len(markdown):
        segments.append((False, markdown[cursor:]))

    return segments


def normalize_markdown(markdown: str) -> str:
    """Normalize line endings and trailing whitespace."""

    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    normalized = WHITESPACE_PATTERN.sub(" ", normalized)
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = BLANK_LINE_PATTERN.sub("\n\n", normalized)
    return normalized.strip()


def remove_cookie_banner_sections(markdown: str) -> str:
    """Remove cookie and consent banner sections."""

    return _remove_blocks(markdown, {"cookie", "cookies", "consent", "accept all", "privacy settings"})


def remove_navigation_sections(markdown: str) -> str:
    """Remove navigation boilerplate sections."""

    return _remove_blocks(markdown, {"navigation", "menu", "nav", "breadcrumb"})


def remove_footer_sections(markdown: str) -> str:
    """Remove footer boilerplate sections."""

    return _remove_blocks(markdown, {"footer", "all rights reserved", "copyright", "site map"})


def remove_advertisement_sections(markdown: str) -> str:
    """Remove advertisement boilerplate sections."""

    return _remove_blocks(markdown, {"advertisement", "sponsored", "promo", "advert", "ad choices"})


def remove_duplicate_paragraphs(markdown: str) -> str:
    """Remove repeated paragraph-level blocks while preserving the first occurrence."""

    blocks = _split_blocks(markdown)
    seen: set[str] = set()
    kept: list[str] = []
    for block in blocks:
        signature = _signature(block)
        if not signature or signature in seen:
            continue

        seen.add(signature)
        kept.append(block)

    return _join_blocks(kept)


def remove_duplicate_headings(markdown: str) -> str:
    """Remove repeated headings while preserving the first occurrence."""

    blocks = _split_blocks(markdown)
    seen: set[str] = set()
    kept: list[str] = []
    for block in blocks:
        if _is_heading_only_block(block):
            heading = _heading_signature(block)
            if heading in seen:
                continue

            seen.add(heading)

        kept.append(block)

    return _join_blocks(kept)


def remove_empty_sections(markdown: str) -> str:
    """Remove headings that do not introduce meaningful body content."""

    blocks = _split_blocks(markdown)
    kept: list[str] = []
    for index, block in enumerate(blocks):
        if not _is_heading_only_block(block):
            kept.append(block)
            continue

        has_meaningful_following_block = False
        for following in blocks[index + 1 :]:
            if _is_heading_only_block(following):
                break
            if following.strip():
                has_meaningful_following_block = True
                break

        if has_meaningful_following_block:
            kept.append(block)

    return _join_blocks(kept)


def remove_repeated_whitespace(markdown: str) -> str:
    """Collapse repeated blank lines after deterministic filtering."""

    return BLANK_LINE_PATTERN.sub("\n\n", markdown).strip()


def _remove_blocks(markdown: str, keywords: set[str]) -> str:
    segments = _split_code_fences(markdown)
    rewritten: list[str] = []
    for is_code, segment in segments:
        if is_code:
            rewritten.append(segment)
            continue

        blocks = _split_blocks(segment)
        kept = [block for block in blocks if not _block_contains_keywords(block, keywords)]
        rewritten.append(_join_blocks(kept))

    return normalize_markdown("".join(rewritten))


def _block_contains_keywords(block: str, keywords: set[str]) -> bool:
    lowered = block.lower()
    return any(keyword in lowered for keyword in keywords)


def _split_blocks(markdown: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", markdown) if block.strip()]
    return blocks


def _join_blocks(blocks: list[str]) -> str:
    return "\n\n".join(blocks).strip()


def _signature(block: str) -> str:
    return re.sub(r"\s+", " ", block).strip().lower()


def _is_heading_only_block(block: str) -> bool:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    return len(lines) == 1 and bool(HEADING_PATTERN.match(lines[0]))


def _heading_signature(block: str) -> str:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if not lines:
        return ""

    match = HEADING_PATTERN.match(lines[0])
    if not match:
        return ""

    return re.sub(r"\s+", " ", match.group(1)).strip().lower()
