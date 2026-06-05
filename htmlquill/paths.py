"""Shared path and environment helpers for htmlquill."""

from __future__ import annotations

import os
from pathlib import Path


def env_flag(name: str) -> bool:
    """Check if an environment variable is set to a truthy value."""
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def default_config_dir() -> Path:
    """Return the default XDG-compatible config directory for htmlquill."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg).expanduser() / "htmlquill"
    return Path("~/.config/htmlquill").expanduser()


def default_config_path() -> Path:
    """Return the default configuration file path."""
    return default_config_dir() / "config.toml"


def default_auth_path(config_dir: Path | None = None) -> Path:
    """Return default auth file path."""
    base_dir = config_dir if config_dir is not None else default_config_dir()
    return base_dir / "auth.json"
