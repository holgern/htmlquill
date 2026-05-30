"""Preview command implementation."""

from __future__ import annotations

import json

import typer

from htmlquill.commands.analyse import load_markdown_for_analysis
from htmlquill.config import BrowserMode
from htmlquill.preview import terminal_preview


def preview_command(
    *,
    source: str,
    max_lines: int | None,
    plain: bool,
    json_summary: bool,
    timeout: float | None,
    user_agent: str | None,
    browser: BrowserMode | None,
    config: str | None,
    no_config: bool,
    auth_file: str | None,
    no_auth: bool,
    profile: str | None,
) -> None:
    markdown = load_markdown_for_analysis(
        source,
        input_mode="auto",
        timeout=timeout,
        user_agent=user_agent,
        browser=browser,
        config=config,
        no_config=no_config,
        auth_file=auth_file,
        no_auth=no_auth,
        profile=profile,
    )
    result = terminal_preview(markdown, max_lines=max_lines, plain=plain)

    if json_summary:
        typer.echo(
            json.dumps(
                {
                    "rendered": result.rendered,
                    "warning": result.warning,
                    "lines": len(result.text.splitlines()),
                    "chars": len(result.text),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    if result.warning:
        typer.echo(result.warning, err=True)
    typer.echo(result.text, nl=False)
