"""Tests for htmlquill.core — integration-level HTML-to-Markdown tests."""

from __future__ import annotations

from htmlquill.core import html_to_markdown


class TestBasicConversion:
    def test_heading_and_paragraph(self) -> None:
        html = "<main><h1>Hello</h1><p>This is <strong>important</strong>.</p></main>"
        md = html_to_markdown(html)
        expected = "# Hello\n\nThis is **important**.\n"
        assert md == expected

    def test_emphasis(self) -> None:
        html = "<p>This is <em>emphasized</em> text.</p>"
        md = html_to_markdown(html)
        assert "*emphasized*" in md

    def test_title_prepend(self) -> None:
        html = "<p>Content.</p>"
        md = html_to_markdown(html, title="My Title")
        assert md.startswith("# My Title\n\n")

    def test_base_url_link_resolution(self) -> None:
        html = '<p><a href="/docs">Docs</a></p>'
        md = html_to_markdown(html, base_url="https://example.com/path/page.html")
        assert "[Docs](https://example.com/docs)" in md


class TestCleanup:
    def test_script_removed(self) -> None:
        html = "<body><p>Keep</p><script>alert(1)</script></body>"
        md = html_to_markdown(html)
        assert "alert" not in md
        assert "Keep" in md

    def test_style_removed(self) -> None:
        html = "<body><p>Keep</p><style>.x{color:red}</style></body>"
        md = html_to_markdown(html)
        assert ".x" not in md
        assert "Keep" in md

    def test_nav_removed(self) -> None:
        html = "<body><nav>Skip</nav><main><p>Keep</p></main></body>"
        md = html_to_markdown(html)
        assert "Skip" not in md
        assert "Keep" in md

    def test_footer_removed(self) -> None:
        html = "<body><footer>Footer</footer><main><p>Keep</p></main></body>"
        md = html_to_markdown(html)
        assert "Footer" not in md

    def test_hidden_element_removed(self) -> None:
        html = "<body><div hidden>Hidden</div><main><p>Keep</p></main></body>"
        md = html_to_markdown(html)
        assert "Hidden" not in md

    def test_aria_hidden_removed(self) -> None:
        html = (
            '<body><div aria-hidden="true">Hidden</div><main><p>Keep</p></main></body>'
        )
        md = html_to_markdown(html)
        assert "Hidden" not in md

    def test_display_none_removed(self) -> None:
        html = (
            '<body><div style="display: none">Hidden</div>'
            "<main><p>Keep</p></main></body>"
        )
        md = html_to_markdown(html)
        assert "Hidden" not in md

    def test_nested_styled_hidden_nodes_do_not_crash(self) -> None:
        html = (
            '<body><div style="display:none"><span style="color:red">'
            "Hidden</span></div><main><p>Visible</p></main></body>"
        )
        md = html_to_markdown(html)
        assert "Visible" in md
        assert "Hidden" not in md

    def test_main_preferred_over_body(self) -> None:
        html = (
            "<body><nav>Nav</nav><main><p>Main content</p></main>"
            "<p>Body content</p></body>"
        )
        md = html_to_markdown(html)
        assert "Main content" in md
        assert "Nav" not in md

    def test_article_preferred_over_body(self) -> None:
        html = "<body><nav>Nav</nav><article><p>Article content</p></article></body>"
        md = html_to_markdown(html)
        assert "Article content" in md
        assert "Nav" not in md

    def test_noscript_removed(self) -> None:
        html = "<body><noscript>Enable JS</noscript><main><p>Keep</p></main></body>"
        md = html_to_markdown(html)
        assert "Enable JS" not in md

    def test_svg_removed(self) -> None:
        html = "<body><svg><circle/></svg><main><p>Keep</p></main></body>"
        md = html_to_markdown(html)
        assert "Keep" in md

    def test_template_removed(self) -> None:
        html = (
            "<body><template><div>Template</div></template>"
            "<main><p>Keep</p></main></body>"
        )
        md = html_to_markdown(html)
        assert "Template" not in md


class TestLists:
    def test_unordered_list(self) -> None:
        html = "<ul><li>One</li><li>Two</li></ul>"
        md = html_to_markdown(html)
        assert "- One\n- Two\n" == md

    def test_ordered_list(self) -> None:
        html = "<ol><li>First</li><li>Second</li></ol>"
        md = html_to_markdown(html)
        assert "1. First\n2. Second\n" == md


class TestCodeBlocks:
    def test_pre_code_block(self) -> None:
        html = '<pre><code>print("hello")</code></pre>'
        md = html_to_markdown(html)
        assert md.startswith("```")
        assert 'print("hello")' in md


class TestMixedContent:
    def test_full_page(self) -> None:
        html = """<!doctype html>
<html>
  <head><title>Test</title></head>
  <body>
    <nav>navigation should be removed</nav>
    <main>
      <h1>Smoke Test</h1>
      <p>Hello <strong>Markdown</strong>.</p>
      <p><a href="/docs">Docs</a></p>
    </main>
    <script>alert(1)</script>
  </body>
</html>"""
        md = html_to_markdown(html, base_url="https://example.com")
        assert "# Smoke Test" in md
        assert "**Markdown**" in md
        assert "[Docs](https://example.com/docs)" in md
        assert "navigation" not in md
        assert "alert" not in md
