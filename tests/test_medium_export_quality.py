"""Medium export quality regression tests.

These tests define the desired target quality for regenerated test.md output.
They should initially fail against the current fixture, then pass after fixes
are applied to the cleaner, renderer, and fetcher.
"""

from __future__ import annotations

from pathlib import Path

from htmlquill.core import html_to_markdown

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "test.md"


def _fixture_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


class TestMediumFixtureQuality:
    """Quality checks against the test.md fixture.

    These will initially FAIL with the current fixture.
    After applying all fixes and regenerating test.md they should pass.
    """

    def test_no_empty_links(self) -> None:
        import re

        text = _fixture_text()
        # Match []() that is NOT part of ![]() (image without alt)
        assert not re.search(r"(?<!!)\[\]\(", text), (
            "Fixture contains empty Markdown links []()"
        )

    def test_no_interaction_placeholders(self) -> None:
        text = _fixture_text()
        assert "Press enter or click to view image in full size" not in text, (
            "Fixture contains Medium image accessibility placeholder text"
        )

    def test_no_medium_signin_actions(self) -> None:
        text = _fixture_text()
        assert "medium.com/m/signin" not in text, (
            "Fixture contains Medium sign-in action URLs"
        )


class TestEmptyLinkRendering:
    """Verify the renderer removes empty links but keeps image-wrapped links."""

    def test_empty_link_text_is_removed(self) -> None:
        html = '<p><a href="https://example.com"></a></p>'
        md = html_to_markdown(html)
        assert "[](" not in md
        assert md.strip() == ""

    def test_empty_link_with_image_still_renders(self) -> None:
        html = '<a href="/x"><img src="/i.png" alt="I"></a>'
        md = html_to_markdown(html, base_url="https://e.test")
        assert "[![I](https://e.test/i.png)](https://e.test/x)" in md

    def test_link_with_only_whitespace_text_removed(self) -> None:
        html = '<p><a href="https://example.com">   </a></p>'
        md = html_to_markdown(html)
        assert "[](" not in md


class TestContentRootSelection:
    """Verify content root selection prefers article over main."""

    def test_article_preferred_over_main_when_both_exist(self) -> None:
        html = (
            "<main>"
            "<a href='/login'>Login</a>"
            "<article><h1>Title</h1><p>Body</p></article>"
            "</main>"
        )
        md = html_to_markdown(html)
        assert "# Title" in md
        assert "Body" in md
        assert "Login" not in md


class TestActionCleanup:
    """Verify action/control elements are cleaned from output."""

    def test_noise_text_removed(self) -> None:
        html = (
            "<article>"
            "<p>Press enter or click to view image in full size</p>"
            "<p>Real content</p>"
            "</article>"
        )
        md = html_to_markdown(html)
        assert "Press enter or click to view image in full size" not in md
        assert "Real content" in md

    def test_medium_signin_link_removed(self) -> None:
        html = (
            "<article>"
            '<a href="https://medium.com/m/signin?operation=register">Sign in</a>'
            "<p>Content</p>"
            "</article>"
        )
        md = html_to_markdown(html)
        assert "medium.com/m/signin" not in md
        assert "Content" in md

    def test_role_button_anchor_without_content_removed(self) -> None:
        html = (
            '<article><a href="/action" role="button">  </a><p>Keep this</p></article>'
        )
        md = html_to_markdown(html)
        assert "/action" not in md
        assert "Keep this" in md


class TestCodeBlockReconstruction:
    """Verify code block reconstruction handles Medium-style line wrappers."""

    def test_pre_with_div_lines(self) -> None:
        html = "<pre><code><div>line 1</div><div>line 2</div><div>line 3</div></code></pre>"
        md = html_to_markdown(html)
        assert "line 1\nline 2\nline 3" in md

    def test_pre_with_p_lines(self) -> None:
        html = "<pre><code><p>line 1</p><p>line 2</p></code></pre>"
        md = html_to_markdown(html)
        assert "line 1\nline 2" in md

    def test_pre_preserves_existing_newlines(self) -> None:
        html = "<pre><code>line 1\nline 2\nline 3</code></pre>"
        md = html_to_markdown(html)
        assert "line 1\nline 2\nline 3" in md


class TestImageExtraction:
    """Verify image extraction supports data-src and picture/source/srcset."""

    def test_image_data_src(self) -> None:
        html = '<img data-src="/img.png" alt="Alt">'
        md = html_to_markdown(html, base_url="https://e.test")
        assert "![Alt](https://e.test/img.png)" in md

    def test_image_data_original(self) -> None:
        html = '<img data-original="/photo.jpg" alt="Photo">'
        md = html_to_markdown(html, base_url="https://e.test")
        assert "![Photo](https://e.test/photo.jpg)" in md

    def test_picture_source_srcset_picks_largest(self) -> None:
        html = (
            "<picture>"
            '<source srcset="/small.png 320w, /large.png 1280w">'
            '<img alt="Alt">'
            "</picture>"
        )
        md = html_to_markdown(html, base_url="https://e.test")
        assert "![Alt](https://e.test/large.png)" in md

    def test_image_srcset_picks_largest(self) -> None:
        html = (
            '<img src="/fallback.png" srcset="/sm.png 320w, /lg.png 1280w" alt="Alt">'
        )
        md = html_to_markdown(html, base_url="https://e.test")
        assert "![Alt](https://e.test/lg.png)" in md

    def test_image_falls_back_to_src_when_no_srcset(self) -> None:
        html = '<img src="/img.png" alt="Alt">'
        md = html_to_markdown(html, base_url="https://e.test")
        assert "![Alt](https://e.test/img.png)" in md
