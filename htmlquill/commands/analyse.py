"""Analyse command implementation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

import click
import typer

from htmlquill.analyse import MarkdownStats, count_markdown_stats
from htmlquill.config import BrowserMode
from htmlquill.core import html_to_markdown, url_to_markdown
from htmlquill.urls import is_url

InputMode = Literal["auto", "markdown", "html"]


def load_markdown_for_analysis(
    source: str,
    *,
    input_mode: InputMode,
    timeout: float | None,
    user_agent: str | None,
    browser: BrowserMode | None,
    config: str | None,
    no_config: bool,
    auth_file: str | None,
    no_auth: bool,
    profile: str | None,
) -> str:
    if source == "-":
        raw = sys.stdin.read()
        if input_mode == "html":
            return html_to_markdown(raw)
        if input_mode == "markdown":
            return raw
        if raw.lstrip().startswith("<"):
            return html_to_markdown(raw)
        return raw

    if is_url(source):
        if input_mode == "markdown":
            raise click.ClickException(
                "--input markdown is not supported for URL sources"
            )
        headers = {"User-Agent": user_agent} if user_agent else None
        config_input: bool | str = False if no_config else (config or True)
        auth_input: bool | str = False if no_auth else (auth_file or True)
        return url_to_markdown(
            source,
            timeout=timeout,
            headers=headers,
            browser=browser,
            config=config_input,
            auth=auth_input,
            profile=profile,
        )

    path = Path(source)
    text = path.read_text(encoding="utf-8")
    lower_suffix = path.suffix.lower()

    if input_mode == "markdown":
        return text
    if input_mode == "html":
        return html_to_markdown(text, base_url=path.resolve().as_uri())

    if lower_suffix in {".md", ".markdown"}:
        return text
    if lower_suffix in {".html", ".htm"}:
        return html_to_markdown(text, base_url=path.resolve().as_uri())

    return text


def render_stats_table(stats: MarkdownStats) -> str:
    payload = stats.to_dict()
    lines: list[str] = []
    for key in sorted(payload):
        lines.append(f"{key}: {payload[key]}")
    return "\n".join(lines)


def analyse_command(
    *,
    source: str,
    input_mode: InputMode,
    timeout: float | None,
    user_agent: str | None,
    browser: BrowserMode | None,
    config: str | None,
    no_config: bool,
    auth_file: str | None,
    no_auth: bool,
    profile: str | None,
    json_output: bool,
) -> None:
    markdown = load_markdown_for_analysis(
        source,
        input_mode=input_mode,
        timeout=timeout,
        user_agent=user_agent,
        browser=browser,
        config=config,
        no_config=no_config,
        auth_file=auth_file,
        no_auth=no_auth,
        profile=profile,
    )
    stats = count_markdown_stats(markdown)
    if json_output:
        typer.echo(json.dumps(stats.to_dict(), indent=2, sort_keys=True))
    else:
        typer.echo(render_stats_table(stats))
