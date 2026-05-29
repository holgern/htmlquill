"""htmlquill — HTML to Markdown converter."""

from __future__ import annotations

from htmlquill._version import __version__, version
from htmlquill.core import html_to_markdown, url_to_markdown

__all__ = ["__version__", "version", "html_to_markdown", "url_to_markdown"]
