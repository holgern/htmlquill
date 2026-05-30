"""Convert command implementation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from htmlquill.config import BrowserMode
from htmlquill.core import (
    html_to_markdown,
    resolve_url_context,
    resolved_context_to_dict,
    url_to_markdown,
)
from htmlquill.urls import is_url


def convert_command(
    source: str,
    output: str | None,
    timeout: float | None,
    user_agent: str | None,
    browser: BrowserMode | None,
    config: str | None,
    no_config: bool,
    auth_file: str | None,
    no_auth: bool,
    profile: str | None,
    print_config: bool,
) -> None:
    if source == "-":
        if print_config:
            raise typer.BadParameter("--print-config requires a URL source")
        markdown = html_to_markdown(sys.stdin.read())
    elif is_url(source):
        headers = {"User-Agent": user_agent} if user_agent else None
        config_input: bool | str = False if no_config else (config or True)
        auth_input: bool | str = False if no_auth else (auth_file or True)

        if print_config:
            context = resolve_url_context(
                source,
                timeout=timeout,
                headers=headers,
                browser=browser,
                config=config_input,
                auth=auth_input,
                profile=profile,
            )
            payload = resolved_context_to_dict(context, headers=headers)
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
            return

        markdown = url_to_markdown(
            source,
            timeout=timeout,
            headers=headers,
            browser=browser,
            config=config_input,
            auth=auth_input,
            profile=profile,
        )
    else:
        if print_config:
            raise typer.BadParameter("--print-config requires a URL source")
        path = Path(source)
        markdown = html_to_markdown(
            path.read_text(encoding="utf-8"),
            base_url=path.resolve().as_uri(),
        )

    if output:
        Path(output).write_text(markdown, encoding="utf-8")
    else:
        typer.echo(markdown, nl=False)
