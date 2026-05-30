"""Configuration loading and option resolution for htmlquill."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from htmlquill.challenge import DEFAULT_CHALLENGE_MARKERS

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover on py311+
    import tomli as tomllib  # type: ignore[import-not-found]

BrowserMode = Literal["auto", "requests", "playwright", "chromium"]
VALID_BROWSERS: tuple[BrowserMode, ...] = ("auto", "requests", "playwright", "chromium")
AdapterMode = Literal["html"]
VALID_ADAPTERS: tuple[AdapterMode, ...] = ("html",)


@dataclass(frozen=True)
class DefaultsConfig:
    adapter: AdapterMode = "html"
    browser: BrowserMode = "auto"
    timeout: float = 20.0
    user_agent: str | None = None
    fail_on_challenge: bool = True
    fallback_on_challenge: bool = True


@dataclass(frozen=True)
class SiteConfig:
    adapter: AdapterMode | None = None
    browser: BrowserMode | None = None
    timeout: float | None = None
    user_agent: str | None = None
    auth: str | None = None
    challenge_markers: tuple[str, ...] = ()
    fail_on_challenge: bool | None = None
    fallback_on_challenge: bool | None = None


@dataclass(frozen=True)
class HtmlQuillConfig:
    version: int = 1
    defaults: DefaultsConfig = DefaultsConfig()
    auth_file: str | None = None
    auth_vault_file: str | None = None
    challenge_markers: tuple[str, ...] = ()
    sites: dict[str, SiteConfig] = field(default_factory=dict)
    source_path: Path | None = None


@dataclass(frozen=True)
class CliOverrides:
    browser: BrowserMode | None = None
    timeout: float | None = None
    user_agent: str | None = None
    profile: str | None = None


@dataclass(frozen=True)
class ResolvedOptions:
    adapter: AdapterMode
    browser: BrowserMode
    timeout: float
    headers: dict[str, str]
    auth_profile: str | None
    challenge_markers: tuple[str, ...]
    fail_on_challenge: bool
    fallback_on_challenge: bool


def default_config_dir() -> Path:
    """Return the default XDG-compatible config directory for htmlquill."""

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg).expanduser() / "htmlquill"
    return Path("~/.config/htmlquill").expanduser()


def default_config_path() -> Path:
    """Return the default configuration file path."""

    return default_config_dir() / "config.toml"


def resolve_config_path(path: Path | str | None = None) -> Path:
    """Resolve explicit/env/default config path."""

    if path is not None:
        return Path(path).expanduser()
    env_path = os.environ.get("HTMLQUILL_CONFIG")
    if env_path:
        return Path(env_path).expanduser()
    return default_config_path()


def _parse_browser(value: Any, *, field_name: str) -> BrowserMode:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    lower = value.strip().lower()
    if lower not in VALID_BROWSERS:
        valid = ", ".join(VALID_BROWSERS)
        raise ValueError(
            f"invalid browser value {value!r} for {field_name}; "
            f"expected one of: {valid}"
        )
    return lower


def _parse_adapter(value: Any, *, field_name: str) -> AdapterMode:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    lower = value.strip().lower()
    if lower == "reddit_api":
        raise ValueError(
            "invalid adapter value 'reddit_api' for "
            f"{field_name}; the Reddit API/OAuth adapter was removed. "
            "Use adapter='html' or remove the adapter setting."
        )
    if lower not in VALID_ADAPTERS:
        valid = ", ".join(VALID_ADAPTERS)
        raise ValueError(
            f"invalid adapter value {value!r} for {field_name}; "
            f"expected one of: {valid}"
        )
    return lower


def _to_float(value: Any, *, field_name: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError(f"{field_name} must be a number")


def _to_bool(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a boolean")


def _to_opt_str(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    raise ValueError(f"{field_name} must be a string")


def _to_marker_tuple(value: Any, *, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return tuple(item.strip() for item in value if item.strip())


def _parse_site_config(name: str, raw: Any) -> SiteConfig:
    if not isinstance(raw, dict):
        raise ValueError(f"sites.{name} must be a table")

    adapter = None
    if "adapter" in raw and raw["adapter"] not in (None, ""):
        adapter = _parse_adapter(raw["adapter"], field_name=f"sites.{name}.adapter")

    browser = None
    if "browser" in raw and raw["browser"] not in (None, ""):
        browser = _parse_browser(raw["browser"], field_name=f"sites.{name}.browser")

    timeout = None
    if "timeout" in raw and raw["timeout"] is not None:
        timeout = _to_float(raw["timeout"], field_name=f"sites.{name}.timeout")

    user_agent = _to_opt_str(
        raw.get("user_agent"), field_name=f"sites.{name}.user_agent"
    )
    auth = _to_opt_str(raw.get("auth"), field_name=f"sites.{name}.auth")
    challenge_markers = _to_marker_tuple(
        raw.get("challenge_markers"), field_name=f"sites.{name}.challenge_markers"
    )

    fail_on_challenge = None
    if "fail_on_challenge" in raw and raw["fail_on_challenge"] is not None:
        fail_on_challenge = _to_bool(
            raw["fail_on_challenge"], field_name=f"sites.{name}.fail_on_challenge"
        )

    fallback_on_challenge = None
    if "fallback_on_challenge" in raw and raw["fallback_on_challenge"] is not None:
        fallback_on_challenge = _to_bool(
            raw["fallback_on_challenge"],
            field_name=f"sites.{name}.fallback_on_challenge",
        )

    return SiteConfig(
        adapter=adapter,
        browser=browser,
        timeout=timeout,
        user_agent=user_agent,
        auth=auth,
        challenge_markers=challenge_markers,
        fail_on_challenge=fail_on_challenge,
        fallback_on_challenge=fallback_on_challenge,
    )


def _merge_markers(
    base_markers: tuple[str, ...], override_markers: tuple[str, ...]
) -> tuple[str, ...]:
    seen: set[str] = set()
    merged: list[str] = []

    for marker in (*base_markers, *override_markers):
        lower = marker.lower()
        if lower in seen:
            continue
        seen.add(lower)
        merged.append(marker)
    return tuple(merged)


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config(path: Path | None = None) -> HtmlQuillConfig:
    """Load config TOML from *path* or search path.

    Missing config files are non-fatal and return built-in defaults.
    """

    resolved_path = resolve_config_path(path)
    if not resolved_path.exists():
        return HtmlQuillConfig(source_path=resolved_path)

    try:
        payload = tomllib.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"failed to load config file {resolved_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("config root must be a TOML table")

    defaults_table = payload.get("defaults", {})
    if not isinstance(defaults_table, dict):
        raise ValueError("defaults must be a TOML table")

    defaults_adapter: AdapterMode = "html"
    if "adapter" in defaults_table and defaults_table["adapter"] not in (None, ""):
        defaults_adapter = _parse_adapter(
            defaults_table["adapter"], field_name="defaults.adapter"
        )

    defaults_browser: BrowserMode = "auto"
    if "browser" in defaults_table and defaults_table["browser"] not in (None, ""):
        defaults_browser = _parse_browser(
            defaults_table["browser"], field_name="defaults.browser"
        )

    defaults_timeout = defaults_table.get("timeout", 20.0)
    defaults_user_agent = defaults_table.get("user_agent")
    defaults_fail_on_challenge = defaults_table.get("fail_on_challenge", True)
    defaults_fallback_on_challenge = defaults_table.get("fallback_on_challenge", True)

    defaults = DefaultsConfig(
        adapter=defaults_adapter,
        browser=defaults_browser,
        timeout=_to_float(defaults_timeout, field_name="defaults.timeout"),
        user_agent=_to_opt_str(defaults_user_agent, field_name="defaults.user_agent"),
        fail_on_challenge=_to_bool(
            defaults_fail_on_challenge, field_name="defaults.fail_on_challenge"
        ),
        fallback_on_challenge=_to_bool(
            defaults_fallback_on_challenge,
            field_name="defaults.fallback_on_challenge",
        ),
    )

    paths_table = payload.get("paths", {})
    if not isinstance(paths_table, dict):
        raise ValueError("paths must be a TOML table")
    auth_file = _to_opt_str(paths_table.get("auth_file"), field_name="paths.auth_file")
    auth_vault_file = _to_opt_str(
        paths_table.get("auth_vault_file"), field_name="paths.auth_vault_file"
    )
    challenge_table = payload.get("challenge", {})
    if not isinstance(challenge_table, dict):
        raise ValueError("challenge must be a TOML table")
    challenge_markers = _to_marker_tuple(
        challenge_table.get("markers"), field_name="challenge.markers"
    )

    raw_sites = payload.get("sites", {})
    if not isinstance(raw_sites, dict):
        raise ValueError("sites must be a TOML table")
    sites = {name: _parse_site_config(name, raw) for name, raw in raw_sites.items()}

    version = payload.get("version", 1)
    if not isinstance(version, int):
        raise ValueError("version must be an integer")

    return HtmlQuillConfig(
        version=version,
        defaults=defaults,
        auth_file=auth_file,
        auth_vault_file=auth_vault_file,
        challenge_markers=challenge_markers,
        sites=sites,
        source_path=resolved_path,
    )


def _match_site(
    hostname: str | None, sites: dict[str, SiteConfig]
) -> SiteConfig | None:
    if not hostname:
        return None

    lower_host = hostname.lower()
    matches = [
        (site_name, cfg)
        for site_name, cfg in sites.items()
        if lower_host == site_name.lower()
        or lower_host.endswith(f".{site_name.lower()}")
    ]
    if not matches:
        return None

    # Most specific suffix wins.
    matches.sort(key=lambda item: len(item[0]), reverse=True)
    return matches[0][1]


def _maybe_expand_path(
    value: str | None, *, base_dir: Path | None = None
) -> Path | None:
    if value is None:
        return None
    p = Path(value).expanduser()
    if p.is_absolute() or base_dir is None:
        return p
    return (base_dir / p).resolve()


def resolve_options(
    url: str, config: HtmlQuillConfig, cli: CliOverrides
) -> ResolvedOptions:
    """Resolve effective options for *url* from built-ins, config, env, and CLI."""

    parsed = urlparse(url)
    site = _match_site(parsed.hostname, config.sites)

    adapter: AdapterMode = "html"
    browser: BrowserMode = "auto"
    timeout: float = 20.0
    user_agent: str | None = None
    auth_profile: str | None = None
    fail_on_challenge = True
    fallback_on_challenge = True
    challenge_markers: tuple[str, ...] = DEFAULT_CHALLENGE_MARKERS

    # Global config defaults
    adapter = config.defaults.adapter
    browser = config.defaults.browser
    timeout = config.defaults.timeout
    user_agent = config.defaults.user_agent
    fail_on_challenge = config.defaults.fail_on_challenge
    fallback_on_challenge = config.defaults.fallback_on_challenge
    if config.challenge_markers:
        challenge_markers = _merge_markers(challenge_markers, config.challenge_markers)

    # Site-level overrides
    if site is not None:
        if site.adapter is not None:
            adapter = site.adapter
        if site.browser is not None:
            browser = site.browser
        if site.timeout is not None:
            timeout = site.timeout
        if site.user_agent is not None:
            user_agent = site.user_agent
        if site.auth is not None:
            auth_profile = site.auth
        if site.challenge_markers:
            challenge_markers = _merge_markers(
                challenge_markers, site.challenge_markers
            )
        if site.fail_on_challenge is not None:
            fail_on_challenge = site.fail_on_challenge
        if site.fallback_on_challenge is not None:
            fallback_on_challenge = site.fallback_on_challenge

    # Environment overrides
    env_browser = os.environ.get("HTMLQUILL_BROWSER")
    if env_browser:
        browser = _parse_browser(env_browser, field_name="HTMLQUILL_BROWSER")

    env_timeout = os.environ.get("HTMLQUILL_TIMEOUT")
    if env_timeout:
        try:
            timeout = float(env_timeout)
        except ValueError as exc:
            raise ValueError(
                f"invalid HTMLQUILL_TIMEOUT value {env_timeout!r}"
            ) from exc

    env_user_agent = os.environ.get("HTMLQUILL_USER_AGENT")
    if env_user_agent:
        user_agent = env_user_agent

    # CLI overrides
    if cli.browser is not None:
        browser = cli.browser
    if cli.timeout is not None:
        timeout = cli.timeout
    if cli.user_agent is not None:
        user_agent = cli.user_agent
    if cli.profile is not None:
        auth_profile = cli.profile

    headers: dict[str, str] = {}
    if user_agent:
        headers["User-Agent"] = user_agent

    return ResolvedOptions(
        adapter=adapter,
        browser=browser,
        timeout=timeout,
        headers=headers,
        auth_profile=auth_profile,
        challenge_markers=challenge_markers,
        fail_on_challenge=fail_on_challenge,
        fallback_on_challenge=fallback_on_challenge,
    )


def config_enabled_for_run(no_config: bool) -> bool:
    """Return whether configuration is enabled for this invocation."""

    if no_config:
        return False
    return not _env_flag("HTMLQUILL_NO_CONFIG")


def resolve_config_for_run(
    *,
    no_config: bool,
    explicit_config_path: str | None,
) -> HtmlQuillConfig:
    """Resolve and load config for one CLI/library run."""

    if not config_enabled_for_run(no_config):
        return HtmlQuillConfig(source_path=None)

    path: Path | None
    if explicit_config_path:
        path = Path(explicit_config_path)
    else:
        path = None
    return load_config(path)


def resolve_auth_file_from_config(
    config: HtmlQuillConfig,
    *,
    config_dir: Path | None,
) -> Path | None:
    """Resolve auth file path defined in config, if present."""

    return _maybe_expand_path(config.auth_file, base_dir=config_dir)


def resolve_auth_vault_file_from_config(
    config: HtmlQuillConfig,
    *,
    config_dir: Path | None,
) -> Path | None:
    """Resolve auth vault file path defined in config, if present."""

    return _maybe_expand_path(config.auth_vault_file, base_dir=config_dir)
