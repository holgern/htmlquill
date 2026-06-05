"""Tests for htmlquill.render — DOM-to-Markdown element conversion."""

from __future__ import annotations

from htmlquill.render import MarkdownRenderer, normalize_markdown


def _render(html_fragment: str, *, base_url: str | None = None) -> str:
    """Helper: render an HTML fragment through MarkdownRenderer."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_fragment, "html.parser")
    renderer = MarkdownRenderer(base_url=base_url)
    return normalize_markdown(renderer.render(soup))


# --- Headings ---


class TestHeadings:
    def test_h1(self) -> None:
        md = _render("<h1>Title</h1>")
        assert md == "# Title\n"

    def test_h2(self) -> None:
        md = _render("<h2>Subtitle</h2>")
        assert md == "## Subtitle\n"

    def test_h3(self) -> None:
        md = _render("<h3>Section</h3>")
        assert md == "### Section\n"

    def test_h4(self) -> None:
        md = _render("<h4>Deep</h4>")
        assert md == "#### Deep\n"

    def test_h5(self) -> None:
        md = _render("<h5>Deeper</h5>")
        assert md == "##### Deeper\n"

    def test_h6(self) -> None:
        md = _render("<h6>Deepest</h6>")
        assert md == "###### Deepest\n"


# --- Paragraphs and inline ---


class TestParagraph:
    def test_simple_paragraph(self) -> None:
        md = _render("<p>Hello world</p>")
        assert md == "Hello world\n"

    def test_strong(self) -> None:
        md = _render("<p>This is <strong>important</strong>.</p>")
        assert md == "This is **important**.\n"

    def test_b_alias(self) -> None:
        md = _render("<p>This is <b>bold</b>.</p>")
        assert md == "This is **bold**.\n"

    def test_em(self) -> None:
        md = _render("<p>This is <em>emphasized</em>.</p>")
        assert md == "This is *emphasized*.\n"

    def test_i_alias(self) -> None:
        md = _render("<p>This is <i>italic</i>.</p>")
        assert md == "This is *italic*.\n"

    def test_inline_code(self) -> None:
        md = _render("<p>Use <code>pip install</code>.</p>")
        assert md == "Use `pip install`.\n"


# --- Links ---


class TestLinks:
    def test_link_with_base_url(self) -> None:
        md = _render(
            '<p><a href="/docs">Docs</a></p>',
            base_url="https://example.com/path/page.html",
        )
        assert md == "[Docs](https://example.com/docs)\n"

    def test_absolute_link(self) -> None:
        md = _render(
            '<p><a href="https://other.com">Other</a></p>',
            base_url="https://example.com",
        )
        assert md == "[Other](https://other.com)\n"

    def test_javascript_link_stripped(self) -> None:
        md = _render('<p><a href="javascript:void(0)">Click</a></p>')
        assert md == "Click\n"

    def test_mailto_link_stripped(self) -> None:
        md = _render('<p><a href="mailto:user@example.com">Email</a></p>')
        assert md == "Email\n"

    def test_empty_href_returns_text(self) -> None:
        md = _render('<p><a href="">Text</a></p>')
        assert md == "Text\n"


# --- Images ---


class TestImages:
    def test_image_with_alt(self) -> None:
        md = _render(
            '<img src="/img/photo.png" alt="A photo">',
            base_url="https://example.com",
        )
        assert md == "![A photo](https://example.com/img/photo.png)\n"

    def test_image_no_src(self) -> None:
        md = _render('<img alt="no src">')
        assert md == "\n"


# --- Lists ---


class TestLists:
    def test_unordered_list(self) -> None:
        md = _render("<ul><li>One</li><li>Two</li></ul>")
        assert md == "- One\n- Two\n"

    def test_ordered_list(self) -> None:
        md = _render("<ol><li>First</li><li>Second</li></ol>")
        assert md == "1. First\n2. Second\n"

    def test_nested_list(self) -> None:
        html = "<ul><li>Item<ul><li>Sub</li></ul></li></ul>"
        md = _render(html)
        assert md == "- Item\n  - Sub\n"


# --- Code blocks ---


class TestCodeBlocks:
    def test_pre_code(self) -> None:
        md = _render('<pre><code>print("hello")</code></pre>')
        assert md == '```\nprint("hello")\n```\n'

    def test_pre_code_with_language(self) -> None:
        md = _render('<pre><code class="language-python">print("hello")</code></pre>')
        assert md == '```python\nprint("hello")\n```\n'

    def test_pre_without_code(self) -> None:
        md = _render("<pre>plain text</pre>")
        assert md == "```\nplain text\n```\n"


# --- Block elements ---


class TestBlockElements:
    def test_blockquote(self) -> None:
        md = _render("<blockquote>This is quoted</blockquote>")
        assert md == "> This is quoted\n"

    def test_hr(self) -> None:
        md = _render("<p>Above</p><hr><p>Below</p>")
        assert "---" in md
        assert "Above" in md
        assert "Below" in md

    def test_br(self) -> None:
        md = _render("<p>Line one<br>Line two</p>")
        assert "Line one" in md
        assert "Line two" in md
        assert "Line one\nLine two" in md


# --- Tables ---


class TestTables:
    def test_simple_table(self) -> None:
        html = (
            "<table><tr><th>Name</th><th>Value</th></tr>"
            "<tr><td>a</td><td>1</td></tr></table>"
        )
        md = _render(html)
        assert "| Name | Value |" in md
        assert "| --- | --- |" in md
        assert "| a | 1 |" in md


# --- Normalize ---


class TestNormalize:
    def test_trailing_newline(self) -> None:
        result = normalize_markdown("hello")
        assert result.endswith("\n")

    def test_collapse_blank_lines(self) -> None:
        result = normalize_markdown("a\n\n\n\nb")
        assert result == "a\n\nb\n"

    def test_strip_trailing_whitespace(self) -> None:
        result = normalize_markdown("hello  \nworld  ")
        first_line = result.split("\n")[0]
        assert first_line == "hello"


# --- Escaping ---


class TestEscaping:
    def test_text_with_special_chars(self) -> None:
        md = _render("<p>Text with *asterisks* and _underscores_</p>")
        # Special chars should be escaped
        assert "\\*" in md
        assert "\\_" in md

    def test_text_with_hash(self) -> None:
        md = _render("<p>Use #hashtag</p>")
        assert "\\#" in md

    def test_text_with_backtick(self) -> None:
        md = _render("<p>Use `code` here</p>")
        # Backticks in text are escaped
        assert "\\`" in md

    def test_link_with_parens_in_url(self) -> None:
        md = _render(
            '<p><a href="https://example.com/page_(1)">Link</a></p>',
            base_url="https://example.com",
        )
        # Parentheses in URL should be encoded
        assert "%28" in md or "%29" in md

    def test_link_label_with_bracket(self) -> None:
        md = _render(
            '<p><a href="https://example.com">Label [1]</a></p>',
            base_url="https://example.com",
        )
        # Bracket in label is NOT escaped to preserve nested image syntax
        assert "[Label [1]](https://example.com)" in md

    def test_image_alt_with_bracket(self) -> None:
        md = _render(
            '<img src="/img.png" alt="Image [1]">',
            base_url="https://example.com",
        )
        # Bracket in alt text should be escaped
        assert "\\]" in md

    def test_table_cell_with_pipe(self) -> None:
        html = "<table><tr><th>A | B</th></tr><tr><td>cell | val</td></tr></table>"
        md = _render(html)
        # Pipes in table cells should be escaped
        assert "\\|" in md

    def test_code_not_over_escaped(self) -> None:
        md = _render("<p>Use <code>*not bold*</code> here</p>")
        # Inside code, asterisks should NOT be escaped
        assert "`*not bold*`" in md

    def test_pre_block_not_over_escaped(self) -> None:
        md = _render("<pre><code>*bold* and _italic_</code></pre>")
        # Inside pre/code, special chars should NOT be escaped
        assert "*bold* and _italic_" in md
