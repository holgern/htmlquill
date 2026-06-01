"""Regression tests for arXiv/LaTeXML-style HTML rendering."""

from __future__ import annotations

import re

from htmlquill.core import html_to_markdown

BAD_PATTERNS = [
    r"→\\rightarrow→",
    r"italic_[A-Za-z]",
    r"^- •",
    r"^\d+\. \d+\.",
]


def test_mathml_annotation_does_not_duplicate_arrow() -> None:
    html = """
    <article><h4>Entities <math alttext="\\rightarrow"><semantics>
      <mo>→</mo><annotation encoding="application/x-tex">\\rightarrow</annotation>
    </semantics></math> Graph</h4></article>
    """
    md = html_to_markdown(html)
    assert "→\\rightarrow" not in md
    assert "\\rightarrow" not in md
    assert "#### Entities → Graph" in md


def test_inline_variable_math_prefers_alttext() -> None:
    html = """
    <article><p>number of users <math alttext="K"><semantics>
      <mi>K</mi><annotation encoding="application/x-tex">K</annotation>
    </semantics></math>.</p></article>
    """
    md = html_to_markdown(html)
    assert "KK" not in md
    assert "italic_" not in md
    assert "$K$" in md


def test_latexml_unordered_bullet_label_is_not_duplicated() -> None:
    html = '<article><ul><li><span class="ltx_tag">•</span> Entity text</li></ul></article>'
    md = html_to_markdown(html)
    assert "- •" not in md
    assert md == "- Entity text\n"


def test_latexml_ordered_label_is_not_duplicated() -> None:
    html = (
        '<article><ol><li><span class="ltx_tag">1.</span> '
        "Describe personas</li></ol></article>"
    )
    md = html_to_markdown(html)
    assert "1. 1." not in md
    assert md == "1. Describe personas\n"


def test_table_cell_newlines_become_br() -> None:
    html = """
    <article><table>
      <tr><th>Dataset</th><th>Questions</th></tr>
      <tr><td>Podcast</td><td>User<br/>Task<br/>1. Question</td></tr>
    </table></article>
    """
    md = html_to_markdown(html)
    assert "| Podcast | User<br>Task<br>1. Question |" in md


def test_table_pipes_are_escaped() -> None:
    html = "<article><table><tr><th>A</th></tr><tr><td>x | y</td></tr></table></article>"
    md = html_to_markdown(html)
    assert "x \\| y" in md


def test_complex_table_falls_back_to_html() -> None:
    html = """
    <article>
      <table>
        <tr><th>Col A</th><th>Col B</th></tr>
        <tr><td colspan="2">Merged content</td></tr>
      </table>
    </article>
    """
    md = html_to_markdown(html)
    assert "<table>" in md
    assert "colspan=\"2\"" in md


def test_figure_caption_and_svg_are_preserved() -> None:
    html = """
    <article>
      <svg><title>decorative icon</title></svg>
      <figure>
        <svg>
          <title>Scatter plot</title>
          <desc>topic frequencies by source</desc>
        </svg>
        <figcaption>Figure 2: Topic distribution overview.</figcaption>
      </figure>
    </article>
    """
    md = html_to_markdown(html)
    assert "decorative icon" not in md
    assert "[SVG figure: Scatter plot topic frequencies by source]" in md
    assert "**Figure 2: Topic distribution overview.**" in md


def test_latexml_artifact_regression_fixture() -> None:
    html = """
    <article>
      <h4>Entities &amp; Relationships <math alttext="\\rightarrow"><semantics>
          <mo>→</mo><annotation encoding="application/x-tex">\\rightarrow</annotation>
      </semantics></math> Knowledge Graph</h4>
      <ol>
        <li><span class="ltx_tag">1.</span> Describe personas.</li>
      </ol>
      <ul>
        <li><span class="ltx_tag">•</span> The entity NeoChip appears.</li>
      </ul>
      <p>number of users <math alttext="K"><semantics>
        <mi>K</mi><annotation encoding="application/x-tex">italic_K</annotation>
      </semantics></math>.</p>
    </article>
    """
    md = html_to_markdown(html)

    for pattern in BAD_PATTERNS:
        assert re.search(pattern, md, flags=re.MULTILINE) is None

    assert "Entities & Relationships → Knowledge Graph" in md
    assert "$K$" in md
