"""Doctor command."""

from __future__ import annotations

import json

import typer

from htmlquill.config import BrowserMode
from htmlquill.doctor import doctor_exit_code, run_doctor


def doctor_command(
    *,
    url: str | None,
    profile: str | None,
    config: str | None,
    auth_file: str | None,
    timeout: float | None,
    user_agent: str | None,
    browser: BrowserMode | None,
    strict_auth_permissions: bool,
    fetch: bool,
    strict: bool,
    json_output: bool,
) -> int:
    checks = run_doctor(
        config_path=config,
        auth_file=auth_file,
        profile=profile,
        strict_auth_permissions=strict_auth_permissions,
        url=url,
        timeout=timeout,
        user_agent=user_agent,
        browser=browser,
        fetch=fetch,
    )

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "checks": [check.to_dict() for check in checks],
                    "exit_code": doctor_exit_code(checks, strict=strict),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for check in checks:
            typer.echo(f"[{check.status}] {check.name}: {check.message}")

    return doctor_exit_code(checks, strict=strict)
