"""Convert command implementation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from htmlquill.commands.helpers import (
    auth_input_from_cli,
    config_input_from_cli,
    headers_from_user_agent,
)
from htmlquill.config import BrowserMode
from htmlquill.core import (
    html_to_markdown,
    resolve_url_context,
    resolved_context_to_dict,
    url_to_markdown,
)
from htmlquill.filenames import markdown_filename, unique_generated_path
from htmlquill.urls import is_url


def _validate_convert_options(
    *,
    source: str,
    output: str | None,
    stdout: bool,
    filename_only: bool,
    filename_max_length: int,
    output_dir: str | None,
    print_config: bool,
) -> None:
    """Validate convert command options and raise BadParameter on conflicts."""
    if filename_max_length < 8:
        raise typer.BadParameter("--filename-max-length must be at least 8")

    if stdout and filename_only:
        raise typer.BadParameter("--stdout and --filename-only cannot be used together")
    if stdout and output:
        raise typer.BadParameter("--stdout and --output cannot be used together")
    if output and output_dir:
        raise typer.BadParameter("--output-dir cannot be used with --output")

    if print_config and source == "-":
        raise typer.BadParameter("--print-config requires a URL source")
    if print_config and not is_url(source):
        raise typer.BadParameter("--print-config requires a URL source")


def _convert_source_to_markdown(
    source: str,
    *,
    timeout: float | None,
    user_agent: str | None,
    browser: BrowserMode | None,
    config: str | None,
    no_config: bool,
    auth_file: str | None,
    no_auth: bool,
    profile: str | None,
    print_config: bool,
) -> str:
    """Load source and convert to Markdown. Returns markdown string."""
    if source == "-":
        return html_to_markdown(sys.stdin.read())

    if is_url(source):
        headers = headers_from_user_agent(user_agent)
        config_input = config_input_from_cli(config, no_config)
        auth_input = auth_input_from_cli(auth_file, no_auth)

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
            raise typer.Exit()

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
    return html_to_markdown(
        path.read_text(encoding="utf-8"),
        base_url=path.resolve().as_uri(),
    )


def _resolve_convert_target(
    *,
    markdown: str,
    source: str,
    output: str | None,
    output_dir: str | None,
    filename_max_length: int,
    force: bool,
) -> Path:
    """Resolve the output file path."""
    if output:
        return Path(output)

    base_dir = Path(output_dir) if output_dir else Path.cwd()
    target = base_dir / markdown_filename(
        markdown,
        source=source,
        max_length=filename_max_length,
    )
    if not force:
        target = unique_generated_path(target)
    return target


def _write_or_print_result(
    *,
    markdown: str,
    target: Path,
    stdout: bool,
    filename_only: bool,
) -> None:
    """Write markdown to file or print to stdout."""
    if stdout:
        typer.echo(markdown, nl=False)
        return

    if filename_only:
        typer.echo(str(target))
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    typer.echo(str(target))


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
    _validate_convert_options(
        source=source,
        output=output,
        stdout=stdout,
        filename_only=filename_only,
        filename_max_length=filename_max_length,
        output_dir=output_dir,
        print_config=print_config,
    )

    markdown = _convert_source_to_markdown(
        source,
        timeout=timeout,
        user_agent=user_agent,
        browser=browser,
        config=config,
        no_config=no_config,
        auth_file=auth_file,
        no_auth=no_auth,
        profile=profile,
        print_config=print_config,
    )

    target = _resolve_convert_target(
        markdown=markdown,
        source=source,
        output=output,
        output_dir=output_dir,
        filename_max_length=filename_max_length,
        force=force,
    )

    _write_or_print_result(
        markdown=markdown,
        target=target,
        stdout=stdout,
        filename_only=filename_only,
    )
