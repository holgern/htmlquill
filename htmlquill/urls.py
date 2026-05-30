"""URL utility helpers."""

from __future__ import annotations

from urllib.parse import urlparse


def is_url(value: str) -> bool:
    """Return ``True`` if *value* looks like an HTTP(S) URL."""

    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
