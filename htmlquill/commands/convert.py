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
from htmlquill.filenames import markdown_filename, unique_generated_path
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
    stdout: bool,
    filename_only: bool,
    filename_max_length: int,
    output_dir: str | None,
    force: bool,
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

    if filename_max_length < 8:
        raise typer.BadParameter("--filename-max-length must be at least 8")

    if stdout and filename_only:
        raise typer.BadParameter("--stdout and --filename-only cannot be used together")
    if stdout and output:
        raise typer.BadParameter("--stdout and --output cannot be used together")
    if output and output_dir:
        raise typer.BadParameter("--output-dir cannot be used with --output")

    if stdout:
        typer.echo(markdown, nl=False)
        return

    if output:
        target = Path(output)
    else:
        base_dir = Path(output_dir) if output_dir else Path.cwd()
        target = base_dir / markdown_filename(
            markdown,
            source=source,
            max_length=filename_max_length,
        )
        if not force:
            target = unique_generated_path(target)

    if filename_only:
        typer.echo(str(target))
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    typer.echo(str(target))
