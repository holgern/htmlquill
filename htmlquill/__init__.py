"""htmlquill — HTML to Markdown converter."""

from __future__ import annotations

try:
    from htmlquill._version import __version__, version
except ImportError:
    __version__ = version = "0.0.0+unknown"
from htmlquill.core import html_to_markdown, url_to_markdown

__all__ = ["__version__", "version", "html_to_markdown", "url_to_markdown"]
