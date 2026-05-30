"""Command-line interface for htmlquill."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

from htmlquill.core import html_to_markdown, url_to_markdown


def is_url(value: str) -> bool:
    """Return ``True`` if *value* looks like an HTTP(S) URL."""
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="htmlquill",
        description="Convert HTML or a URL to Markdown.",
    )
    parser.add_argument(
        "source",
        help="URL, HTML file path, or '-' for stdin",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Markdown output path. Defaults to stdout.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds (default: 20)",
    )
    parser.add_argument(
        "--user-agent",
        help="Custom HTTP User-Agent header",
    )
    parser.add_argument(
        "--browser",
        choices=["auto", "requests", "playwright"],
        default="auto",
        help="Fetching mode: auto (default), requests, or playwright (requires htmlquill[browser])",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the htmlquill CLI.

    Returns
    -------
    int
        Exit code: 0 on success, 1 on error.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.source == "-":
            markdown = html_to_markdown(sys.stdin.read())
        elif is_url(args.source):
            headers = {"User-Agent": args.user_agent} if args.user_agent else None
            markdown = url_to_markdown(
                args.source, timeout=args.timeout, headers=headers, browser=args.browser
            )
        else:
            path = Path(args.source)
            markdown = html_to_markdown(
                path.read_text(encoding="utf-8"), base_url=path.as_uri()
            )

        if args.output:
            Path(args.output).write_text(markdown, encoding="utf-8")
        else:
            sys.stdout.write(markdown)
        return 0
    except Exception as exc:
        print(f"htmlquill: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
