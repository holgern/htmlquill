"""Typer-based command-line interface for htmlquill."""

from __future__ import annotations

import sys
from collections.abc import Sequence

import click
import typer

from htmlquill.commands.analyse import analyse_command
from htmlquill.commands.auth import app as auth_app
from htmlquill.commands.config import app as config_app
from htmlquill.commands.convert import convert_command
from htmlquill.commands.doctor import doctor_command
from htmlquill.commands.preview import preview_command
from htmlquill.config import BrowserMode

app = typer.Typer(
    name="htmlquill",
    help="Convert HTML or URLs to Markdown.",
    no_args_is_help=True,
)

KNOWN_COMMANDS = {
    "convert",
    "config",
    "auth",
    "doctor",
    "analyse",
    "analyze",
    "preview",
}


@app.command("convert")
def convert(
    source: str = typer.Argument(..., help="URL, HTML file path, or '-' for stdin"),
    output: str | None = typer.Option(None, "-o", "--output"),
    timeout: float | None = typer.Option(None, "--timeout"),
    user_agent: str | None = typer.Option(None, "--user-agent"),
    browser: BrowserMode | None = typer.Option(None, "--browser"),
    config: str | None = typer.Option(
        None,
        "--config",
        help="Load this config.toml instead of the default search path",
    ),
    no_config: bool = typer.Option(False, "--no-config", help="Ignore config files"),
    auth_file: str | None = typer.Option(
        None,
        "--auth-file",
        help="Load this auth.json instead of the configured/default path",
    ),
    no_auth: bool = typer.Option(False, "--no-auth", help="Disable auth loading"),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Force a named auth/site profile for this fetch",
    ),
    print_config: bool = typer.Option(
        False,
        "--print-config",
        help="Deprecated; use `htmlquill config show URL`.",
    ),
    stdout_opt: bool = typer.Option(
        False,
        "--stdout",
        help="Print converted Markdown to stdout and do not save.",
    ),
    filename_only: bool = typer.Option(
        False,
        "--filename-only",
        help="Print the resolved output filename and do not save.",
    ),
    filename_max_length: int = typer.Option(
        80,
        "--filename-max-length",
        help="Maximum generated filename stem length, excluding .md.",
    ),
    output_dir: str | None = typer.Option(
        None,
        "--output-dir",
        help="Directory for generated filenames. Ignored when --output is used.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite generated output file instead of adding a numeric suffix.",
    ),
) -> None:
    convert_command(
        source,
        output,
        timeout,
        user_agent,
        browser,
        config,
        no_config,
        auth_file,
        no_auth,
        profile,
        print_config,
        stdout_opt,
        filename_only,
        filename_max_length,
        output_dir,
        force,
    )


@app.command("doctor")
def doctor(
    url: str | None = typer.Option(
        None,
        "--url",
        help="URL to inspect (no fetch by default)",
    ),
    profile: str | None = typer.Option(None, "--profile"),
    config: str | None = typer.Option(None, "--config"),
    auth_file: str | None = typer.Option(None, "--auth-file"),
    timeout: float | None = typer.Option(None, "--timeout"),
    user_agent: str | None = typer.Option(None, "--user-agent"),
    browser: BrowserMode | None = typer.Option(None, "--browser"),
    strict_auth_permissions: bool = typer.Option(
        False,
        "--strict-auth-permissions",
        help="Treat auth file permission issues as errors.",
    ),
    fetch: bool = typer.Option(
        False,
        "--fetch",
        help="Run a network fetch smoke test when --url is provided.",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Return exit code 2 if warnings are present.",
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    exit_code = doctor_command(
        url=url,
        profile=profile,
        config=config,
        auth_file=auth_file,
        timeout=timeout,
        user_agent=user_agent,
        browser=browser,
        strict_auth_permissions=strict_auth_permissions,
        fetch=fetch,
        strict=strict,
        json_output=json_output,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@app.command("analyse")
def analyse(
    source: str = typer.Argument(..., help="URL, HTML/Markdown file, or '-'"),
    input_mode: str = typer.Option("auto", "--input", help="Input interpretation."),
    timeout: float | None = typer.Option(None, "--timeout"),
    user_agent: str | None = typer.Option(None, "--user-agent"),
    browser: BrowserMode | None = typer.Option(None, "--browser"),
    config: str | None = typer.Option(None, "--config"),
    no_config: bool = typer.Option(False, "--no-config"),
    auth_file: str | None = typer.Option(None, "--auth-file"),
    no_auth: bool = typer.Option(False, "--no-auth"),
    profile: str | None = typer.Option(None, "--profile"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    analyse_command(
        source=source,
        input_mode=input_mode,  # type: ignore[arg-type]
        timeout=timeout,
        user_agent=user_agent,
        browser=browser,
        config=config,
        no_config=no_config,
        auth_file=auth_file,
        no_auth=no_auth,
        profile=profile,
        json_output=json_output,
    )


app.command("analyze")(analyse)


@app.command("preview")
def preview(
    source: str = typer.Argument(..., help="URL, HTML/Markdown file, or '-'"),
    max_lines: int | None = typer.Option(None, "--max-lines"),
    plain: bool = typer.Option(False, "--plain"),
    json_summary: bool = typer.Option(False, "--json-summary"),
    timeout: float | None = typer.Option(None, "--timeout"),
    user_agent: str | None = typer.Option(None, "--user-agent"),
    browser: BrowserMode | None = typer.Option(None, "--browser"),
    config: str | None = typer.Option(None, "--config"),
    no_config: bool = typer.Option(False, "--no-config"),
    auth_file: str | None = typer.Option(None, "--auth-file"),
    no_auth: bool = typer.Option(False, "--no-auth"),
    profile: str | None = typer.Option(None, "--profile"),
) -> None:
    preview_command(
        source=source,
        max_lines=max_lines,
        plain=plain,
        json_summary=json_summary,
        timeout=timeout,
        user_agent=user_agent,
        browser=browser,
        config=config,
        no_config=no_config,
        auth_file=auth_file,
        no_auth=no_auth,
        profile=profile,
    )


app.add_typer(config_app, name="config")
app.add_typer(auth_app, name="auth")


def _normalize_argv(argv: Sequence[str]) -> list[str]:
    args = list(argv)
    if not args:
        return args

    if args[0] in KNOWN_COMMANDS:
        return args

    if args[0] in {"-h", "--help"}:
        return args

    return ["convert", *args]


def main(argv: list[str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv
    args = _normalize_argv(raw_args)

    try:
        command = typer.main.get_command(app)
        command.main(args=args, prog_name="htmlquill", standalone_mode=False)
        return 0
    except click.ClickException as exc:
        exc.show()
        return int(exc.exit_code)
    except typer.Exit as exc:
        code = exc.exit_code
        return int(code if code is not None else 0)
    except Exception as exc:  # pragma: no cover - defensive
        typer.echo(f"htmlquill: error: {exc}", err=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
