"""Public API for htmlquill — HTML to Markdown conversion."""

from __future__ import annotations

from collections.abc import Mapping

from htmlquill.clean import parse_and_clean
from htmlquill.fetch import BrowserMode, fetch_html
from htmlquill.render import MarkdownRenderer, normalize_markdown


def html_to_markdown(
    html: str,
    *,
    base_url: str | None = None,
    title: str | None = None,
) -> str:
    """Convert an HTML document or fragment to Markdown.

    Parameters
    ----------
    html
        Raw HTML string.
    base_url
        Optional base URL for resolving relative links and images.
    title
        Optional title to prepend as an ``<h1>`` heading.

    Returns
    -------
    str
        Normalized Markdown text.
    """
    root = parse_and_clean(html)
    renderer = MarkdownRenderer(base_url=base_url)
    markdown = renderer.render(root)
    if title:
        markdown = f"# {title}\n\n{markdown}"
    return normalize_markdown(markdown)


def url_to_markdown(
    url: str,
    *,
    timeout: float = 20.0,
    headers: Mapping[str, str] | None = None,
    browser: BrowserMode = "auto",
) -> str:
    """Fetch a URL and convert the response HTML to Markdown.

    Parameters
    ----------
    url
        The URL to fetch.
    timeout
        HTTP request timeout in seconds.
    headers
        Optional custom HTTP headers.
    browser
        Fetching mode: ``"auto"``, ``"requests"``, or ``"playwright"``.
        See :func:`fetch_html` for details.

    Returns
    -------
    str
        Normalized Markdown text.
    """
    html = fetch_html(url, timeout=timeout, headers=headers, browser=browser)
    return html_to_markdown(html, base_url=url)
