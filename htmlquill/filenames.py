"""Filename generation helpers for converted Markdown output."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlparse

_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`([^`]*)`")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_WORD_RE = re.compile(r"[a-z0-9]+")


def first_markdown_heading(markdown: str) -> str | None:
    """Return the first H1 text, falling back to the first heading."""

    first_any: str | None = None
    for match in _ATX_HEADING_RE.finditer(markdown):
        level = len(match.group(1))
        text = _strip_inline_markdown(match.group(2).strip())
        if not text:
            continue
        if first_any is None:
            first_any = text
        if level == 1:
            return text
    return first_any


def fallback_title_from_source(source: str | None) -> str:
    if not source or source == "-":
        return "untitled"

    parsed = urlparse(source)
    if parsed.scheme and parsed.netloc:
        path_part = Path(unquote(parsed.path)).stem
        if path_part:
            return path_part
        return parsed.netloc

    path = Path(source)
    if path.stem:
        return path.stem
    return "untitled"


def filename_stem_from_title(title: str, *, max_length: int = 80) -> str:
    if max_length < 8:
        raise ValueError("max_length must be at least 8")

    normalized = unicodedata.normalize("NFKD", title)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    lower = ascii_text.lower()

    words = _WORD_RE.findall(lower)
    stem = "-".join(words).strip("-")
    if not stem:
        stem = "untitled"

    stem = stem[:max_length].rstrip("-")
    return stem or "untitled"


def markdown_filename(
    markdown: str,
    *,
    source: str | None = None,
    max_length: int = 80,
) -> str:
    title = first_markdown_heading(markdown) or fallback_title_from_source(source)
    return f"{filename_stem_from_title(title, max_length=max_length)}.md"


def unique_generated_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    for index in range(2, 10_000):
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate

    raise FileExistsError(f"could not find a free filename near {path}")


def _strip_inline_markdown(text: str) -> str:
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = _IMAGE_RE.sub(r"\1", text)
    text = _LINK_RE.sub(r"\1", text)
    text = text.replace("*", "").replace("_", "").replace("~", "")
    return " ".join(text.split())
