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

NOISE_TEXTS = {
    "Press enter or click to view image in full size",
}

ACTION_HREF_PARTS = (
    "/m/signin",
    "operation=register",
)


def _drop_action_controls(root: BeautifulSoup | Tag) -> None:
    """Remove action control elements from the DOM."""
    # Drop anchors that point to action/sign-in flows
    for a in list(root.find_all("a")):
        href = str(a.get("href", ""))
        if any(part in href for part in ACTION_HREF_PARTS):
            a.decompose()
            continue
        # Drop empty anchors without images that have role=button
        if a.get("role") == "button":
            has_img = a.find("img") is not None
            if not has_img and not a.get_text(strip=True):
                a.decompose()


def _drop_noise_text_nodes(root: BeautifulSoup | Tag) -> None:
    """Remove known noise text from the DOM."""
    for text_node in list(root.find_all(string=True)):
        if str(text_node).strip() in NOISE_TEXTS:
            # Remove the parent element if it only contains noise
            parent = text_node.parent
            if parent is not None and isinstance(parent, Tag):
                parent_text = parent.get_text(strip=True)
                if parent_text in NOISE_TEXTS:
                    parent.decompose()
                else:
                    text_node.extract()
            else:
                text_node.extract()


def _content_score(node: Tag) -> int:
    """Score a candidate content root by content density."""
    score = 0
    score += len(node.find_all("p")) * 3
    score += len(node.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])) * 2
    text_len = len(node.get_text(strip=True))
    score += text_len // 100
    # Penalize nodes with many action/sign-in links
    action_links = 0
    for a in node.find_all("a"):
        href = str(a.get("href", ""))
        if "/m/signin" in href or "operation=register" in href:
            action_links += 1
    score -= action_links * 5
    return score


def parse_and_clean(html: str) -> BeautifulSoup | Tag:
    """Parse HTML and remove unwanted elements.

    Strips scripts, styles, navigation, footers, hidden elements, and other
    non-content nodes.  Selects the best content container using a
    content-scoring heuristic that prefers ``<article>`` over ``<main>``,
    then ``<body>``, or the whole document.

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

    # Drop action controls and noise text
    _drop_action_controls(soup)
    _drop_noise_text_nodes(soup)
    # Gather content candidates and score them
    candidates: list[Tag] = []
    for tag in soup.find_all("article"):
        candidates.append(tag)
    for tag in soup.find_all("main"):
        candidates.append(tag)
    # Also consider [role=main]
    for tag in soup.select("[role=main]"):
        if tag not in candidates:
            candidates.append(tag)

    if candidates:
        best = max(candidates, key=_content_score)
        return best

    return soup.body or soup
