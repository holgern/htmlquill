"""Authentication/session state helpers for htmlquill."""

from __future__ import annotations

import json
import os
import stat
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from requests.cookies import RequestsCookieJar, create_cookie


@dataclass(frozen=True)
class CookieConfig:
    name: str
    value: str
    domain: str | None = None
    path: str | None = None
    secure: bool = False
    http_only: bool = False


@dataclass(frozen=True)
class AuthProfile:
    name: str
    kind: str
    cookies: tuple[CookieConfig, ...] = ()
    playwright_storage_state: Path | None = None
    chromium_user_data_dir: Path | None = None
    token_env: str | None = None


@dataclass(frozen=True)
class AuthStore:
    version: int = 1
    profiles: dict[str, AuthProfile] = field(default_factory=dict)
    source_path: Path | None = None


@dataclass(frozen=True)
class ResolvedAuth:
    profile_name: str | None = None
    cookies: list[dict[str, object]] | None = None
    playwright_storage_state: str | None = None
    chromium_user_data_dir: str | None = None
    token_env: str | None = None
    bearer_token: str | None = field(default=None, repr=False)
    token_source: str | None = None  # "vault", "env", None


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def default_auth_path(config_dir: Path | None = None) -> Path:
    """Return default auth file path."""

    base_dir = config_dir
    if base_dir is None:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            base_dir = Path(xdg).expanduser() / "htmlquill"
        else:
            base_dir = Path("~/.config/htmlquill").expanduser()
    return base_dir / "auth.json"


def auth_enabled_for_run(no_auth: bool) -> bool:
    """Return whether auth loading is enabled for this invocation."""

    if no_auth:
        return False
    return not _env_flag("HTMLQUILL_NO_AUTH")


def resolve_auth_path(
    *,
    explicit_auth_path: str | Path | None,
    config_auth_path: str | None,
    config_dir: Path | None,
) -> Path:
    """Resolve auth path from explicit path, env, config, or default."""

    if explicit_auth_path is not None:
        return Path(explicit_auth_path).expanduser()

    env_path = os.environ.get("HTMLQUILL_AUTH")
    if env_path:
        return Path(env_path).expanduser()

    if config_auth_path:
        configured = Path(config_auth_path).expanduser()
        if configured.is_absolute() or config_dir is None:
            return configured
        return (config_dir / configured).resolve()

    return default_auth_path(config_dir)


def _warn_or_fail_on_permissions(path: Path, *, strict_permissions: bool) -> None:
    if os.name == "nt":
        return
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        msg = (
            f"auth file {path} is group/world accessible (mode {oct(mode)}); "
            "recommended mode is 0o600"
        )
        if strict_permissions:
            raise PermissionError(msg)
        warnings.warn(msg, stacklevel=2)


def _parse_cookie(index: int, raw: Any) -> CookieConfig:
    if not isinstance(raw, dict):
        raise ValueError(f"cookies[{index}] must be an object")

    name = raw.get("name")
    value = raw.get("value")
    if not isinstance(name, str) or not isinstance(value, str):
        raise ValueError(f"cookies[{index}] requires string 'name' and 'value'")

    domain = raw.get("domain")
    path = raw.get("path")
    secure = bool(raw.get("secure", False))
    http_only = bool(raw.get("httpOnly", raw.get("http_only", False)))

    if domain is not None and not isinstance(domain, str):
        raise ValueError(f"cookies[{index}].domain must be a string")
    if path is not None and not isinstance(path, str):
        raise ValueError(f"cookies[{index}].path must be a string")

    return CookieConfig(
        name=name,
        value=value,
        domain=domain,
        path=path,
        secure=secure,
        http_only=http_only,
    )


def _expand_profile_path(raw_path: Any, *, base_dir: Path) -> Path | None:
    if raw_path in (None, ""):
        return None
    if not isinstance(raw_path, str):
        raise ValueError("profile path values must be strings")
    parsed = Path(raw_path).expanduser()
    if parsed.is_absolute():
        return parsed
    return (base_dir / parsed).resolve()


def _parse_profile(name: str, raw: Any, *, base_dir: Path) -> AuthProfile:
    if not isinstance(raw, dict):
        raise ValueError(f"profiles.{name} must be an object")

    kind = raw.get("kind", "cookies")
    if not isinstance(kind, str):
        raise ValueError(f"profiles.{name}.kind must be a string")

    cookies_data = raw.get("cookies", [])
    if not isinstance(cookies_data, list):
        raise ValueError(f"profiles.{name}.cookies must be an array")
    cookies = tuple(_parse_cookie(i, c) for i, c in enumerate(cookies_data))

    playwright_storage_state = _expand_profile_path(
        raw.get("playwright_storage_state"), base_dir=base_dir
    )
    chromium_user_data_dir = _expand_profile_path(
        raw.get("chromium_user_data_dir"), base_dir=base_dir
    )

    token_env = raw.get("token_env")
    if token_env is not None and not isinstance(token_env, str):
        raise ValueError(f"profiles.{name}.token_env must be a string")

    return AuthProfile(
        name=name,
        kind=kind,
        cookies=cookies,
        playwright_storage_state=playwright_storage_state,
        chromium_user_data_dir=chromium_user_data_dir,
        token_env=token_env,
    )


def load_auth(path: Path, *, strict_permissions: bool = True) -> AuthStore:
    """Load auth JSON from *path*."""

    expanded = path.expanduser()
    _warn_or_fail_on_permissions(expanded, strict_permissions=strict_permissions)

    try:
        payload = json.loads(expanded.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"failed to read auth file {expanded}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse auth file {expanded}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("auth JSON root must be an object")

    version = payload.get("version", 1)
    if not isinstance(version, int):
        raise ValueError("auth version must be an integer")

    profiles_raw = payload.get("profiles", {})
    if not isinstance(profiles_raw, dict):
        raise ValueError("auth profiles must be an object")

    base_dir = expanded.parent
    profiles = {
        profile_name: _parse_profile(profile_name, raw, base_dir=base_dir)
        for profile_name, raw in profiles_raw.items()
    }

    return AuthStore(version=version, profiles=profiles, source_path=expanded)


def resolve_auth_profile(auth_store: AuthStore, name: str | None) -> AuthProfile | None:
    """Resolve one auth profile by *name*."""

    if name is None:
        return None
    if name not in auth_store.profiles:
        available = ", ".join(sorted(auth_store.profiles)) or "(none)"
        raise ValueError(f"auth profile {name!r} not found; available: {available}")
    return auth_store.profiles[name]


def cookies_to_requests_jar(cookies: tuple[CookieConfig, ...]) -> RequestsCookieJar:
    """Convert cookie configs to ``requests`` cookie jar."""

    jar = RequestsCookieJar()
    for cookie in cookies:
        rest: dict[str, Any] = {}
        if cookie.http_only:
            rest["HttpOnly"] = True
        jar.set_cookie(
            create_cookie(
                name=cookie.name,
                value=cookie.value,
                domain=cookie.domain or "",
                path=cookie.path or "/",
                secure=cookie.secure,
                rest=rest,
            )
        )
    return jar


def resolve_auth(
    auth_store: AuthStore | None,
    *,
    profile_name: str | None,
) -> ResolvedAuth:
    """Resolve concrete fetch auth values for an optional auth profile."""

    if auth_store is None:
        return ResolvedAuth(profile_name=None)

    profile = resolve_auth_profile(auth_store, profile_name)
    if profile is None:
        return ResolvedAuth(profile_name=None)

    cookie_payload: list[dict[str, object]] | None = None
    if profile.cookies:
        cookie_payload = [
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
                "secure": cookie.secure,
                "httpOnly": cookie.http_only,
            }
            for cookie in profile.cookies
        ]

    return ResolvedAuth(
        profile_name=profile.name,
        cookies=cookie_payload,
        playwright_storage_state=(
            str(profile.playwright_storage_state)
            if profile.playwright_storage_state is not None
            else None
        ),
        chromium_user_data_dir=(
            str(profile.chromium_user_data_dir)
            if profile.chromium_user_data_dir is not None
            else None
        ),
        token_env=profile.token_env,
    )


def redacted_auth_dict(resolved: ResolvedAuth) -> dict[str, object]:
    """Return a redacted dict suitable for ``--print-config`` output."""

    cookies_count = len(resolved.cookies or [])
    env_has_token = resolved.token_env and os.environ.get(resolved.token_env)
    token_present = bool(resolved.bearer_token or env_has_token)
    return {
        "profile": resolved.profile_name,
        "cookies": "<redacted>" if cookies_count else None,
        "cookies_count": cookies_count,
        "playwright_storage_state": resolved.playwright_storage_state,
        "chromium_user_data_dir": resolved.chromium_user_data_dir,
        "token_env": resolved.token_env,
        "bearer_token": "<redacted>" if resolved.bearer_token else None,
        "token_source": resolved.token_source,
        "token_present": token_present,
    }
