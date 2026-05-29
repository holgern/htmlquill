"""HTTP fetching utilities for htmlquill."""

from __future__ import annotations

from collections.abc import Mapping

import requests

DEFAULT_USER_AGENT = "htmlquill/0.1 (+https://github.com/holgern/htmlquill)"


class FetchError(RuntimeError):
    """Raised when a URL cannot be fetched as HTML."""


def fetch_html(
    url: str,
    *,
    timeout: float = 20.0,
    headers: Mapping[str, str] | None = None,
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

    Returns
    -------
    str
        The HTML content of the response.

    Raises
    ------
    FetchError
        If the request fails or the response does not look like HTML.
    """
    request_headers: dict[str, str] = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        request_headers.update(headers)

    try:
        response = requests.get(url, headers=request_headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"failed to fetch {url!r}: {exc}") from exc

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower() and response.text.lstrip()[:1] != "<":
        raise FetchError(f"URL did not look like HTML: {url!r}")

    return response.text
