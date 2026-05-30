"""HTTP fetching utilities for htmlquill."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

import requests

DEFAULT_USER_AGENT = "htmlquill/0.1 (+https://github.com/holgern/htmlquill)"

BrowserMode = Literal["auto", "requests", "playwright"]


class FetchError(RuntimeError):
    """Raised when a URL cannot be fetched as HTML."""


def _fetch_with_playwright(url: str, *, timeout: float = 20.0) -> str:
    """Fetch a URL using Playwright headless Chromium.

    Parameters
    ----------
    url
        The URL to fetch.
    timeout
        Navigation timeout in seconds.

    Returns
    -------
    str
        The HTML content after JavaScript execution.

    Raises
    ------
    FetchError
        If Playwright is not installed or the page cannot be loaded.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-untyped]
    except ImportError as exc:
        msg = (
            "Playwright is required for browser-based fetching. "
            "Install it with: pip install htmlquill[browser] && playwright install chromium"
        )
        raise FetchError(msg) from exc

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
            html = page.content()
            browser.close()
    except Exception as exc:
        raise FetchError(f"browser fetch failed for {url!r}: {exc}") from exc

    return html


def _looks_like_html(text: str, content_type: str = "") -> bool:
    """Check if the response looks like HTML."""
    if "html" in content_type.lower():
        return True
    return text.lstrip()[:1] == "<"


def fetch_html(
    url: str,
    *,
    timeout: float = 20.0,
    headers: Mapping[str, str] | None = None,
    browser: BrowserMode = "auto",
) -> str:
    """Fetch a URL and return the HTML content as a string.

    Parameters
    ----------
    url
        The URL to fetch.
    timeout
        HTTP request timeout in seconds.
    headers
        Optional custom HTTP headers to merge with the defaults.
    browser
        Fetching mode:

        - ``"requests"`` — plain HTTP via *requests* (the default backend).
        - ``"playwright"`` — always use headless Chromium via Playwright.
        - ``"auto"`` — try *requests* first; on HTTP 403, fall back to
          Playwright if available.

    Returns
    -------
    str
        The HTML content of the response.

    Raises
    ------
    FetchError
        If the request fails or the response does not look like HTML.
    """
    if browser == "playwright":
        html = _fetch_with_playwright(url, timeout=timeout)
        if not _looks_like_html(html):
            raise FetchError(f"browser result did not look like HTML: {url!r}")
        return html

    # --- requests path ---
    request_headers: dict[str, str] = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        request_headers.update(headers)

    try:
        response = requests.get(url, headers=request_headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        # In auto mode, retry with Playwright on 403
        if (
            browser == "auto"
            and isinstance(exc, requests.HTTPError)
            and exc.response is not None
            and exc.response.status_code == 403
        ):
            try:
                html = _fetch_with_playwright(url, timeout=timeout)
                if not _looks_like_html(html):
                    raise FetchError(f"browser result did not look like HTML: {url!r}")  # noqa: TRY301
                return html
            except FetchError:
                # Playwright failed or not installed — raise the original 403
                pass
        raise FetchError(f"failed to fetch {url!r}: {exc}") from exc

    content_type = response.headers.get("content-type", "")
    if not _looks_like_html(response.text, content_type):
        raise FetchError(f"URL did not look like HTML: {url!r}")

    return response.text
