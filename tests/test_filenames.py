"""Tests for htmlquill.filenames."""

from __future__ import annotations

from pathlib import Path

from htmlquill.filenames import (
    fallback_title_from_source,
    filename_stem_from_title,
    first_markdown_heading,
    markdown_filename,
    unique_generated_path,
)


class TestFirstMarkdownHeading:
    def test_prefers_h1_over_earlier_h2(self) -> None:
        md = "## Subtitle\n\n# Main Title\n\nText\n"
        assert first_markdown_heading(md) == "Main Title"

    def test_returns_first_heading_when_no_h1(self) -> None:
        md = "## Subtitle\n\n### Deeper\n"
        assert first_markdown_heading(md) == "Subtitle"

    def test_returns_none_for_no_heading(self) -> None:
        md = "No heading here\n"
        assert first_markdown_heading(md) is None

    def test_strips_inline_markdown(self) -> None:
        md = "# My **Great** [`Post`](https://example.com)\n"
        assert first_markdown_heading(md) == "My Great Post"

    def test_strips_images(self) -> None:
        md = "# ![alt text](image.png) Hello\n"
        # alt text is preserved by _IMAGE_RE substitution
        assert first_markdown_heading(md) == "alt text Hello"

    def test_strips_inline_code(self) -> None:
        md = "# `functionName` explained\n"
        assert first_markdown_heading(md) == "functionName explained"

    def test_skips_empty_heading(self) -> None:
        md = "# **\n\n## Real\n"
        # After stripping ** the first heading is empty, so fallback to h2
        assert first_markdown_heading(md) == "Real"

    def test_uses_first_h1_even_if_later(self) -> None:
        md = "## First\n\n# Second\n\n# Third\n"
        assert first_markdown_heading(md) == "Second"


class TestFallbackTitleFromSource:
    def test_url_path_stem(self) -> None:
        assert (
            fallback_title_from_source("https://example.com/posts/MyArticle.html")
            == "MyArticle"
        )

    def test_url_no_path_uses_netloc(self) -> None:
        assert fallback_title_from_source("https://example.com") == "example.com"

    def test_file_path_stem(self) -> None:
        assert fallback_title_from_source("/tmp/page.html") == "page"

    def test_stdin_returns_untitled(self) -> None:
        assert fallback_title_from_source("-") == "untitled"

    def test_none_returns_untitled(self) -> None:
        assert fallback_title_from_source(None) == "untitled"

    def test_empty_returns_untitled(self) -> None:
        assert fallback_title_from_source("") == "untitled"


class TestFilenameStemFromTitle:
    def test_basic_slug(self) -> None:
        stem = filename_stem_from_title("Hello World")
        assert stem == "hello-world"

    def test_punctuation_removed(self) -> None:
        stem = filename_stem_from_title("Hello, World: 2026!")
        assert stem == "hello-world-2026"

    def test_max_length_no_trailing_dash(self) -> None:
        stem = filename_stem_from_title("one two three four", max_length=13)
        assert stem == "one-two-three"
        assert len(stem) <= 13
        assert not stem.endswith("-")

    def test_max_length_exact(self) -> None:
        stem = filename_stem_from_title("abcdef", max_length=8)
        assert stem == "abcdef"

    def test_max_length_minimum(self) -> None:
        stem = filename_stem_from_title("ok", max_length=8)
        assert stem == "ok"

    def test_max_length_too_small_raises(self) -> None:
        try:
            filename_stem_from_title("test", max_length=7)
            raise AssertionError("Expected ValueError")
        except ValueError as exc:
            assert "at least 8" in str(exc)

    def test_unicode_normalized_to_ascii(self) -> None:
        stem = filename_stem_from_title("Café München")
        assert stem == "cafe-munchen"

    def test_empty_after_strip_returns_untitled(self) -> None:
        stem = filename_stem_from_title("!!!@@@")
        assert stem == "untitled"

    def test_complex_title(self) -> None:
        stem = filename_stem_from_title(
            "My Comprehensive Obsidian Setup: Web Clipper & Bases"
        )
        assert stem == "my-comprehensive-obsidian-setup-web-clipper-bases"


class TestMarkdownFilename:
    def test_from_heading(self) -> None:
        md = "# My Comprehensive Obsidian Setup: Web Clipper & Bases\n"
        assert (
            markdown_filename(md)
            == "my-comprehensive-obsidian-setup-web-clipper-bases.md"
        )

    def test_falls_back_to_url_path(self) -> None:
        md = "No heading here\n"
        assert (
            markdown_filename(md, source="https://example.com/posts/MyArticle.html")
            == "myarticle.md"
        )

    def test_falls_back_to_untitled(self) -> None:
        md = "No heading here\n"
        assert markdown_filename(md) == "untitled.md"

    def test_respects_max_length(self) -> None:
        md = "# one two three four five\n"
        assert markdown_filename(md, max_length=13) == "one-two-three.md"


class TestUniqueGeneratedPath:
    def test_returns_same_when_no_conflict(self, tmp_path: Path) -> None:
        target = tmp_path / "new.md"
        assert unique_generated_path(target) == target

    def test_adds_suffix_on_collision(self, tmp_path: Path) -> None:
        existing = tmp_path / "title.md"
        existing.write_text("old", encoding="utf-8")
        assert unique_generated_path(existing) == tmp_path / "title-2.md"

    def test_increments_past_existing_suffixes(self, tmp_path: Path) -> None:
        (tmp_path / "title.md").write_text("a", encoding="utf-8")
        (tmp_path / "title-2.md").write_text("b", encoding="utf-8")
        assert unique_generated_path(tmp_path / "title.md") == tmp_path / "title-3.md"

    def test_raises_after_many_collisions(self, tmp_path: Path) -> None:
        target = tmp_path / "full.md"
        for i in range(2, 10_001):
            (tmp_path / f"full-{i}.md").write_text("x", encoding="utf-8")
        target.write_text("x", encoding="utf-8")
        try:
            unique_generated_path(target)
            raise AssertionError("Expected FileExistsError")
        except FileExistsError:
            pass
