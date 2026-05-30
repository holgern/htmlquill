"""Unit tests for markdown analysis helpers."""

from __future__ import annotations

from htmlquill.analyse import count_markdown_stats


def test_count_markdown_stats_excludes_images_from_links() -> None:
    md = "![alt](img.png)\n[site](https://example.com)\n"
    stats = count_markdown_stats(md)
    assert stats.images == 1
    assert stats.links == 1


def test_count_markdown_stats_strips_fenced_code_for_inline_and_words() -> None:
    md = """```\n[not-a-link](x) `code`\n```\n
`inline` and words
"""
    stats = count_markdown_stats(md)
    assert stats.code_blocks == 1
    assert stats.inline_code_spans == 1
    assert stats.words >= 2
