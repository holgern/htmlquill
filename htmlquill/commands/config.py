"""Config command group."""

from __future__ import annotations

import json
from pathlib import Path

import click
import typer

from htmlquill.auth import resolve_auth_path
from htmlquill.config import load_config, resolve_config_path
from htmlquill.core import resolve_url_context, resolved_context_to_dict
from htmlquill.urls import is_url

app = typer.Typer(help="Inspect and manage htmlquill configuration.")

_CONFIG_TEMPLATE = """\
version = 1

[defaults]
adapter = "html"
browser = "auto"
timeout = 30.0
# user_agent = "Mozilla/5.0 htmlquill/0.1"
fail_on_challenge = true
fallback_on_challenge = true

[paths]
auth_file = "~/.config/htmlquill/auth.json"
# auth_vault_file is optional and only needed if you use encrypted generic auth data.
# auth_vault_file = "~/.config/htmlquill/auth.vault"

[challenge]
markers = [
  "Performing security verification",
  "verifies you are not a bot",
  "You've been blocked by network security",
  "blocked by network security",
  "If you think you've been blocked by mistake, file a ticket",
]

[sites."medium.com"]
browser = "chromium"
timeout = 60.0
auth = "medium"

[sites."alain-airom.medium.com"]
browser = "chromium"
timeout = 60.0
auth = "medium"
"""


@app.command("path")
def config_path(json_output: bool = typer.Option(False, "--json")) -> None:
    """Print the resolved config file path."""

    path = resolve_config_path()
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "config_path": str(path),
                    "exists": path.exists(),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        typer.echo(path)


@app.command("show")
def config_show(
    url: str = typer.Argument(..., help="URL to resolve effective config for."),
    profile: str | None = typer.Option(None, "--profile"),
    config: str | None = typer.Option(None, "--config"),
    no_config: bool = typer.Option(False, "--no-config"),
    auth_file: str | None = typer.Option(None, "--auth-file"),
    no_auth: bool = typer.Option(False, "--no-auth"),
    timeout: float | None = typer.Option(None, "--timeout"),
    user_agent: str | None = typer.Option(None, "--user-agent"),
    browser: str | None = typer.Option(None, "--browser"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show resolved effective config/auth context for a URL."""

    if not is_url(url):
        raise click.ClickException("config show requires an HTTP(S) URL")

    headers = {"User-Agent": user_agent} if user_agent else None
    config_input: bool | str = False if no_config else (config or True)
    auth_input: bool | str = False if no_auth else (auth_file or True)

    context = resolve_url_context(
        url,
        timeout=timeout,
        headers=headers,
        browser=browser,  # type: ignore[arg-type]
        config=config_input,
        auth=auth_input,
        profile=profile,
    )
    payload = resolved_context_to_dict(context, headers=headers)

    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@app.command("init")
def config_init(
    config: str | None = typer.Option(None, "--config"),
    force: bool = typer.Option(False, "--force"),
    print_only: bool = typer.Option(False, "--print"),
) -> None:
    """Initialize a default config file."""

    path = resolve_config_path(config)
    if print_only:
        typer.echo(_CONFIG_TEMPLATE, nl=False)
        return

    if path.exists() and not force:
        raise click.ClickException(
            f"config file already exists: {path} (use --force to overwrite)"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_CONFIG_TEMPLATE, encoding="utf-8")
    typer.echo(f"wrote config template to {path}")


@app.command("validate")
def config_validate(
    config: str | None = typer.Option(None, "--config"),
    check_auth: bool = typer.Option(True, "--check-auth/--no-check-auth"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Validate config file syntax and references."""

    cfg = load_config(Path(config).expanduser() if config else None)
    warnings: list[str] = []

    if check_auth:
        config_dir = cfg.source_path.parent if cfg.source_path is not None else None
        auth_path = resolve_auth_path(
            explicit_auth_path=None,
            config_auth_path=cfg.auth_file,
            config_dir=config_dir,
        )
        if not auth_path.exists() and cfg.auth_file:
            warnings.append(f"referenced auth file does not exist: {auth_path}")

    payload = {
        "valid": True,
        "config_path": str(cfg.source_path) if cfg.source_path is not None else None,
        "warnings": warnings,
    }

    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        typer.echo("Config is valid.")
        if cfg.source_path is not None:
            typer.echo(f"Path: {cfg.source_path}")
        if warnings:
            for warning in warnings:
                typer.echo(f"Warning: {warning}", err=True)
