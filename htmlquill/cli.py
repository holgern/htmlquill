"""Command-line interface for htmlquill."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from htmlquill.core import (
    html_to_markdown,
    resolve_url_context,
    resolved_context_to_dict,
    url_to_markdown,
)


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
        default=None,
        help="HTTP timeout in seconds (resolved default: 20)",
    )
    parser.add_argument(
        "--user-agent",
        default=None,
        help="Custom HTTP User-Agent header",
    )
    parser.add_argument(
        "--browser",
        choices=["auto", "requests", "playwright", "chromium"],
        default=None,
        help="Fetching mode override: auto, requests, playwright, or chromium",
    )
    parser.add_argument(
        "--config",
        help="Load this config.toml instead of the default search path",
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Ignore config files",
    )
    parser.add_argument(
        "--auth-file",
        help="Load this auth.json instead of the configured/default path",
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Disable auth loading",
    )
    parser.add_argument(
        "--profile",
        help="Force a named auth/site profile for this fetch",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Print resolved effective config for the URL and exit",
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
            if args.print_config:
                raise ValueError("--print-config requires a URL source")
            markdown = html_to_markdown(sys.stdin.read())
        elif is_url(args.source):
            headers = {"User-Agent": args.user_agent} if args.user_agent else None
            config_input: bool | str = (
                False if args.no_config else (args.config or True)
            )
            auth_input: bool | str = False if args.no_auth else (args.auth_file or True)

            if args.print_config:
                context = resolve_url_context(
                    args.source,
                    timeout=args.timeout,
                    headers=headers,
                    browser=args.browser,
                    config=config_input,
                    auth=auth_input,
                    profile=args.profile,
                )
                payload = resolved_context_to_dict(context, headers=headers)
                sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
                return 0

            markdown = url_to_markdown(
                args.source,
                timeout=args.timeout,
                headers=headers,
                browser=args.browser,
                config=config_input,
                auth=auth_input,
                profile=args.profile,
            )
        else:
            if args.print_config:
                raise ValueError("--print-config requires a URL source")
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
