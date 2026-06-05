"""Auth command group."""

from __future__ import annotations

import json
import os
from pathlib import Path

import click
import typer

from htmlquill.auth import (
    load_auth,
    redacted_auth_dict,
    resolve_auth,
    resolve_auth_path,
)
from htmlquill.config import load_config

app = typer.Typer(help="Inspect and manage htmlquill auth profiles.")

_AUTH_TEMPLATE = (
    "{\n"
    '  "version": 1,\n'
    '  "profiles": {\n'
    '    "medium": {\n'
    '      "kind": "browser_state",\n'
    '      "playwright_storage_state": "~/.config/htmlquill/auth/'
    'medium.storage-state.json",\n'
    '      "chromium_user_data_dir": "~/.config/htmlquill/chromium/medium"\n'
    "    }\n"
    "  }\n"
    "}\n"
)


def _resolved_auth_path(
    *,
    auth_file: str | None,
    config: str | None,
) -> Path:
    cfg = load_config(Path(config).expanduser() if config else None)
    config_dir = cfg.source_path.parent if cfg.source_path is not None else None
    return resolve_auth_path(
        explicit_auth_path=auth_file,
        config_auth_path=cfg.auth_file,
        config_dir=config_dir,
    )


@app.command("path")
def auth_path(
    auth_file: str | None = typer.Option(None, "--auth-file"),
    config: str | None = typer.Option(None, "--config"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Print the resolved auth file path."""

    path = _resolved_auth_path(auth_file=auth_file, config=config)
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "auth_path": str(path),
                    "exists": path.exists(),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        typer.echo(path)


@app.command("show")
def auth_show(
    profile: str | None = typer.Option(None, "--profile"),
    auth_file: str | None = typer.Option(None, "--auth-file"),
    config: str | None = typer.Option(None, "--config"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show redacted auth profile metadata."""

    path = _resolved_auth_path(auth_file=auth_file, config=config)
    if not path.exists():
        raise click.ClickException(f"auth file not found: {path}")

    store = load_auth(path, strict_permissions=False)

    if profile:
        resolved = resolve_auth(store, profile_name=profile)
        payload: dict[str, object] = {
            "auth_path": str(path),
            "profile": profile,
            "data": redacted_auth_dict(resolved),
        }
    else:
        profiles: dict[str, object] = {}
        for profile_name in sorted(store.profiles):
            profiles[profile_name] = redacted_auth_dict(
                resolve_auth(store, profile_name=profile_name)
            )
        payload = {
            "auth_path": str(path),
            "profiles": profiles,
        }

    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@app.command("init")
def auth_init(
    auth_file: str | None = typer.Option(None, "--auth-file"),
    config: str | None = typer.Option(None, "--config"),
    force: bool = typer.Option(False, "--force"),
    print_only: bool = typer.Option(False, "--print"),
) -> None:
    """Initialize an auth.json skeleton."""

    path = _resolved_auth_path(auth_file=auth_file, config=config)
    if print_only:
        typer.echo(_AUTH_TEMPLATE, nl=False)
        return

    if path.exists() and not force:
        raise click.ClickException(
            f"auth file already exists: {path} (use --force to overwrite)"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_AUTH_TEMPLATE, encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)
    typer.echo(f"wrote auth template to {path}")


