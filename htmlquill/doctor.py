"""Environment and configuration diagnostics."""

from __future__ import annotations

import importlib.util
import os
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from htmlquill.auth import load_auth, resolve_auth_path
from htmlquill.config import (
    BrowserMode,
    HtmlQuillConfig,
    load_config,
    resolve_config_path,
)
from htmlquill.core import resolve_url_context
from htmlquill.fetch import FetchError, _find_chromium, fetch_html


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str  # "ok", "warn", "error", "info"
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _import_exists(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        return False


def run_doctor(  # noqa: C901
    *,
    config_path: str | None = None,
    auth_file: str | None = None,
    profile: str | None = None,
    strict_auth_permissions: bool = False,
    url: str | None = None,
    timeout: float | None = None,
    user_agent: str | None = None,
    browser: BrowserMode | None = None,
    fetch: bool = False,
) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []

    py_ok = sys.version_info >= (3, 10)
    checks.append(
        DoctorCheck(
            "python",
            "ok" if py_ok else "error",
            f"{platform.python_version()} at {sys.executable}",
        )
    )

    for module in ("bs4", "requests", "typer"):
        available = _import_exists(module)
        checks.append(
            DoctorCheck(
                f"import:{module}",
                "ok" if available else "error",
                "available" if available else "missing",
            )
        )

    config_resolved = resolve_config_path(config_path)
    try:
        cfg = load_config(config_resolved if config_path else None)
        config_state = (
            "exists" if config_resolved.exists() else "not found; using defaults"
        )
        config_status = "ok" if config_resolved.exists() else "info"
        config_message = f"{config_resolved} ({config_state})"
        if cfg.warnings:
            config_status = "warn"
            config_message = f"{config_message}; " + "; ".join(cfg.warnings)
        checks.append(
            DoctorCheck(
                "config",
                config_status,
                config_message,
            )
        )
    except Exception as exc:
        checks.append(DoctorCheck("config", "error", str(exc)))
        cfg = HtmlQuillConfig(source_path=None)

    config_dir = cfg.source_path.parent if cfg.source_path is not None else None
    auth_resolved = resolve_auth_path(
        explicit_auth_path=auth_file,
        config_auth_path=cfg.auth_file,
        config_dir=config_dir,
    )
    if auth_resolved.exists():
        try:
            store = load_auth(auth_resolved, strict_permissions=strict_auth_permissions)
            if profile and profile not in store.profiles:
                checks.append(
                    DoctorCheck(
                        "auth",
                        "error",
                        f"profile {profile!r} not found",
                    )
                )
            else:
                checks.append(DoctorCheck("auth", "ok", f"{auth_resolved}"))
        except PermissionError as exc:
            checks.append(
                DoctorCheck(
                    "auth",
                    "error" if strict_auth_permissions else "warn",
                    str(exc),
                )
            )
        except Exception as exc:
            checks.append(DoctorCheck("auth", "error", str(exc)))
    else:
        checks.append(
            DoctorCheck(
                "auth",
                "warn" if profile else "info",
                f"{auth_resolved} not found",
            )
        )

    chromium = _find_chromium()
    checks.append(
        DoctorCheck(
            "chromium",
            "ok" if chromium else "warn",
            chromium or "not found on PATH",
        )
    )

    playwright_available = _import_exists("playwright.sync_api")
    checks.append(
        DoctorCheck(
            "playwright",
            "ok" if playwright_available else "info",
            "available"
            if playwright_available
            else "optional dependency not installed",
        )
    )

    # --- Secure auth vault checks ---

    vaultconfig_available = _import_exists("vaultconfig.crypt")

    vault_path: Path | None = None
    config_dir_vault = cfg.source_path.parent if cfg.source_path is not None else None
    if cfg.auth_vault_file:
        from htmlquill.config import _maybe_expand_path

        vault_path = _maybe_expand_path(cfg.auth_vault_file, base_dir=config_dir_vault)
    else:
        from htmlquill.vault import default_auth_vault_path

        vault_path = default_auth_vault_path(config_dir_vault)

    # Only report on vaultconfig availability if a vault is in use.
    vault_in_use = vault_path and vault_path.exists()
    if vault_in_use:
        checks.append(
            DoctorCheck(
                "secure_auth_dependency",
                "ok" if vaultconfig_available else "warn",
                "vaultconfig available"
                if vaultconfig_available
                else (
                    "secure auth requires VaultConfig; "
                    'install with: pip install "htmlquill[secure]"'
                ),
            )
        )
    else:
        checks.append(
            DoctorCheck(
                "secure_auth_dependency",
                "info" if not vaultconfig_available else "ok",
                "vaultconfig available"
                if vaultconfig_available
                else "secure auth (optional) requires VaultConfig",
            )
        )

    if vault_in_use:
        checks.append(
            DoctorCheck(
                "secure_auth_vault_exists",
                "ok",
                str(vault_path),
            )
        )

        # Check permissions
        if os.name != "nt":
            import stat

            try:
                mode = stat.S_IMODE(vault_path.stat().st_mode)
                if mode & 0o077:
                    checks.append(
                        DoctorCheck(
                            "secure_auth_permissions",
                            "warn",
                            f"auth vault {vault_path} is group/world accessible "
                            f"(mode {oct(mode)}); recommended mode is 0o600",
                        )
                    )
                else:
                    checks.append(
                        DoctorCheck(
                            "secure_auth_permissions",
                            "ok",
                            "auth vault file permissions are 0600",
                        )
                    )
            except OSError as exc:
                checks.append(
                    DoctorCheck(
                        "secure_auth_permissions",
                        "error",
                        str(exc),
                    )
                )

        # Check encryption
        if vaultconfig_available:
            try:
                raw_bytes = vault_path.read_bytes()
                from vaultconfig import crypt  # type: ignore[import-not-found]

                if crypt.is_encrypted(raw_bytes):
                    checks.append(
                        DoctorCheck(
                            "secure_auth_vault_encrypted",
                            "ok",
                            "auth vault appears encrypted",
                        )
                    )
                else:
                    checks.append(
                        DoctorCheck(
                            "secure_auth_vault_encrypted",
                            "error",
                            "auth vault does not appear to be VaultConfig-encrypted",
                        )
                    )
            except Exception as exc:
                checks.append(
                    DoctorCheck(
                        "secure_auth_vault_encrypted",
                        "error",
                        str(exc),
                    )
                )
        else:
            checks.append(
                DoctorCheck(
                    "secure_auth_vault_encrypted",
                    "info",
                    "vaultconfig not available; cannot check encryption status",
                )
            )
    else:
        checks.append(
            DoctorCheck(
                "secure_auth_vault_exists",
                "info" if not profile else "warn",
                f"{vault_path} {'not found' if vault_path else 'not configured'}",
            )
        )

    if url:
        headers = {"User-Agent": user_agent} if user_agent else None
        config_input: bool | str = config_path or True
        auth_input: bool | str = auth_file or True
        try:
            context = resolve_url_context(
                url,
                timeout=timeout,
                headers=headers,
                browser=browser,
                config=config_input,
                auth=auth_input,
                profile=profile,
            )
            checks.append(
                DoctorCheck(
                    "url_context",
                    "ok",
                    (
                        f"adapter={context.options.adapter}, "
                        f"browser={context.options.browser}, "
                        f"timeout={context.options.timeout}, "
                        f"auth_profile={context.auth.profile_name}"
                    ),
                )
            )

            if fetch:
                try:
                    merged_headers = dict(context.options.headers)
                    if headers:
                        merged_headers.update(headers)
                    fetch_html(
                        url,
                        timeout=context.options.timeout,
                        headers=merged_headers,
                        browser=context.options.browser,
                        cookies=context.auth.cookies,
                        playwright_storage_state=context.auth.playwright_storage_state,
                        chromium_user_data_dir=context.auth.chromium_user_data_dir,
                        challenge_markers=list(context.options.challenge_markers),
                        fallback_on_challenge=context.options.fallback_on_challenge,
                        fail_on_challenge=context.options.fail_on_challenge,
                    )
                    checks.append(
                        DoctorCheck("fetch", "ok", "fetch smoke test succeeded")
                    )
                except FetchError as exc:
                    message = str(exc)
                    status = "warn" if "rate limited; reset=" in message else "error"
                    checks.append(DoctorCheck("fetch", status, message))
                except Exception as exc:
                    checks.append(DoctorCheck("fetch", "error", str(exc)))
        except Exception as exc:
            checks.append(DoctorCheck("url_context", "error", str(exc)))

    return checks


def doctor_exit_code(checks: list[DoctorCheck], *, strict: bool = False) -> int:
    has_error = any(check.status == "error" for check in checks)
    if has_error:
        return 1
    has_warn = any(check.status == "warn" for check in checks)
    if strict and has_warn:
        return 2
    return 0
