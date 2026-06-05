"""Shared CLI helpers for htmlquill commands."""

from __future__ import annotations

from dataclasses import dataclass

from htmlquill.config import BrowserMode


@dataclass(frozen=True)
class SourceOptions:
    """Common CLI options for URL sources."""

    timeout: float | None = None
    user_agent: str | None = None
    browser: BrowserMode | None = None
    config: str | None = None
    no_config: bool = False
    auth_file: str | None = None
    no_auth: bool = False
    profile: str | None = None


def headers_from_user_agent(user_agent: str | None) -> dict[str, str] | None:
    """Build headers dict from user agent string."""
    if user_agent:
        return {"User-Agent": user_agent}
    return None


def config_input_from_cli(config: str | None, no_config: bool) -> bool | str:
    """Resolve config input from CLI flags."""
    if no_config:
        return False
    return config or True


def auth_input_from_cli(auth_file: str | None, no_auth: bool) -> bool | str:
    """Resolve auth input from CLI flags."""
    if no_auth:
        return False
    return auth_file or True
