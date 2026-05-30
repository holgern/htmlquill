"""Markdown analysis helpers."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MarkdownStats:
    lines: int
    nonblank_lines: int
    chars: int
    words: int
    headings: int
    headings_by_level: dict[str, int]
    code_blocks: int
    inline_code_spans: int
    images: int
    links: int
    tables: int
    blockquotes: int
    list_items: int
    frontmatter: bool
    estimated_reading_minutes: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_HEADING_RE = re.compile(r"^(#{1,6})\s+\S", re.MULTILINE)
_FENCED_CODE_RE = re.compile(r"(^|\n)```.*?\n.*?(\n```|$)", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\([^)]+\)")
_INLINE_CODE_RE = re.compile(r"(?<!`)`[^`\n]+`(?!`)")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^\s*>\s?", re.MULTILINE)
_TABLE_SEPARATOR_RE = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$"
)


def _strip_fenced_code(markdown: str) -> str:
    return _FENCED_CODE_RE.sub("\n", markdown)


def count_markdown_stats(markdown: str) -> MarkdownStats:
    lines = markdown.splitlines()
    nonblank = [line for line in lines if line.strip()]

    headings_by_level = {f"h{i}": 0 for i in range(1, 7)}
    for match in _HEADING_RE.finditer(markdown):
        headings_by_level[f"h{len(match.group(1))}"] += 1

    without_blocks = _strip_fenced_code(markdown)
    words = len(re.findall(r"\b[\w'-]+\b", without_blocks))

    tables = sum(
        1 for i in range(1, len(lines)) if _TABLE_SEPARATOR_RE.match(lines[i])
    )

    return MarkdownStats(
        lines=len(lines),
        nonblank_lines=len(nonblank),
        chars=len(markdown),
        words=words,
        headings=sum(headings_by_level.values()),
        headings_by_level=headings_by_level,
        code_blocks=sum(1 for _ in _FENCED_CODE_RE.finditer(markdown)),
        inline_code_spans=len(_INLINE_CODE_RE.findall(without_blocks)),
        images=len(_IMAGE_RE.findall(markdown)),
        links=len(_LINK_RE.findall(markdown)),
        tables=tables,
        blockquotes=len(_BLOCKQUOTE_RE.findall(markdown)),
        list_items=len(_LIST_ITEM_RE.findall(markdown)),
        frontmatter=markdown.startswith("---\n"),
        estimated_reading_minutes=max(1, math.ceil(words / 220)) if words else 0,
    )
