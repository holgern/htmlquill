"""HTML parsing and cleanup for htmlquill."""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

DROP_SELECTORS = [
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "nav",
    "footer",
    "[hidden]",
    '[aria-hidden="true"]',
]


def parse_and_clean(html: str) -> BeautifulSoup | Tag:
    """Parse HTML and remove unwanted elements.

    Strips scripts, styles, navigation, footers, hidden elements, and other
    non-content nodes.  Selects the best content container in order of
    preference: ``<main>``, ``<article>``, ``<body>``, or the whole document.

    Parameters
    ----------
    html
        Raw HTML string to parse.

    Returns
    -------
    BeautifulSoup | Tag
        The cleaned root element ready for rendering.
    """
    soup = BeautifulSoup(html, "html.parser")

    for selector in DROP_SELECTORS:
        for node in soup.select(selector):
            node.decompose()

    for node in soup.find_all(style=True):
        style = str(node.get("style", "")).replace(" ", "").lower()
        if "display:none" in style or "visibility:hidden" in style:
            node.decompose()

    return soup.find("main") or soup.find("article") or soup.body or soup
