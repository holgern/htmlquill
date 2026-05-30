"""Encrypted auth vault read/write using VaultConfig."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _import_vaultconfig_crypt():  # type: ignore[no-untyped-def]
    """Lazy-import vaultconfig.crypt with an actionable error message."""
    try:
        from vaultconfig import crypt  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "secure auth requires VaultConfig; "
            'install with: pip install "htmlquill[secure]"'
        ) from exc
    return crypt


@dataclass(frozen=True)
class VaultProfile:
    """A named profile inside the encrypted vault."""

    name: str
    kind: str
    data: dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class AuthVault:
    """Decrypted auth vault content."""

    version: int
    profiles: dict[str, VaultProfile]
    source_path: Path


def default_auth_vault_path(config_dir: Path | None = None) -> Path:
    """Return the default auth vault file path."""
    base_dir = config_dir
    if base_dir is None:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            base_dir = Path(xdg).expanduser() / "htmlquill"
        else:
            base_dir = Path("~/.config/htmlquill").expanduser()
    return base_dir / "auth.vault"


def resolve_auth_vault_path(
    *,
    explicit_vault_path: str | Path | None,
    config_vault_path: str | None,
    config_dir: Path | None,
) -> Path:
    """Resolve the auth vault path from explicit, config, or default."""
    if explicit_vault_path is not None:
        return Path(explicit_vault_path).expanduser()

    env_path = os.environ.get("HTMLQUILL_VAULT_FILE")
    if env_path:
        return Path(env_path).expanduser()

    if config_vault_path:
        configured = Path(config_vault_path).expanduser()
        if configured.is_absolute() or config_dir is None:
            return configured
        return (config_dir / configured).resolve()

    return default_auth_vault_path(config_dir)


def get_vault_password(prompt: str = "HtmlQuill vault password: ") -> str:
    """Resolve the vault password from env vars or interactive prompt.

    Priority order:
    1. HTMLQUILL_VAULT_PASSWORD
    2. HTMLQUILL_VAULT_PASSWORD_COMMAND
    3. VAULTCONFIG_PASSWORD
    4. VAULTCONFIG_PASSWORD_COMMAND
    5. interactive getpass prompt
    """
    # 1. HTMLQUILL_VAULT_PASSWORD
    env_val = os.environ.get("HTMLQUILL_VAULT_PASSWORD")
    if env_val:
        return env_val

    # 2. HTMLQUILL_VAULT_PASSWORD_COMMAND
    cmd = os.environ.get("HTMLQUILL_VAULT_PASSWORD_COMMAND")
    if cmd:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass  # fall through to next source

    # 3. VAULTCONFIG_PASSWORD
    env_val = os.environ.get("VAULTCONFIG_PASSWORD")
    if env_val:
        return env_val

    # 4. VAULTCONFIG_PASSWORD_COMMAND
    cmd = os.environ.get("VAULTCONFIG_PASSWORD_COMMAND")
    if cmd:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass  # fall through to interactive

    # 5. interactive prompt
    import getpass

    return getpass.getpass(prompt)


def _secure_write(path: Path, data: bytes) -> None:
    """Write *data* atomically to *path* with mode 0600."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(tmp, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        if os.name != "nt":
            path.chmod(0o600)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def _warn_if_not_encrypted(data: bytes, path: Path) -> None:
    """Warn if data does not appear to be VaultConfig-encrypted."""
    crypt = _import_vaultconfig_crypt()
    if not crypt.is_encrypted(data):
        import warnings

        warnings.warn(
            f"auth vault {path} does not appear to be encrypted; "
            "tokens will be stored in plaintext",
            stacklevel=3,
        )


def _check_permissions(path: Path) -> None:
    """Warn if vault file has insecure permissions on POSIX."""
    if os.name == "nt":
        return
    import stat

    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return
    if mode & 0o077:
        import warnings

        warnings.warn(
            f"auth vault {path} is group/world accessible (mode {oct(mode)}); "
            "recommended mode is 0o600",
            stacklevel=3,
        )


def load_auth_vault(
    path: Path,
    *,
    password: str | None = None,
    prompt: bool = True,
) -> AuthVault:
    """Load and decrypt an auth vault file."""
    crypt = _import_vaultconfig_crypt()
    expanded = path.expanduser()

    if not expanded.exists():
        raise FileNotFoundError(f"auth vault not found: {expanded}")

    _check_permissions(expanded)

    try:
        raw = expanded.read_bytes()
    except OSError as exc:
        raise OSError(f"failed to read auth vault {expanded}: {exc}") from exc

    if password is None and prompt:
        password = get_vault_password()

    if password is None:
        raise ValueError("vault password is required to decrypt the auth vault")

    try:
        plaintext = crypt.decrypt(raw, password)
    except crypt.DecryptionError as exc:
        raise ValueError(f"failed to decrypt auth vault {expanded}: {exc}") from exc

    try:
        payload = json.loads(plaintext)
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse decrypted vault JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("auth vault root must be a JSON object")

    version = payload.get("version", 1)
    if not isinstance(version, int):
        raise ValueError("auth vault version must be an integer")

    profiles_raw = payload.get("profiles", {})
    if not isinstance(profiles_raw, dict):
        raise ValueError("auth vault profiles must be an object")

    profiles: dict[str, VaultProfile] = {}
    for name, raw in profiles_raw.items():
        if not isinstance(raw, dict):
            raise ValueError(f"vault profile {name!r} must be an object")
        kind = raw.get("kind", "")
        profiles[name] = VaultProfile(name=name, kind=str(kind), data=dict(raw))

    return AuthVault(version=version, profiles=profiles, source_path=expanded)


def save_auth_vault(
    path: Path,
    payload: dict[str, Any],
    *,
    password: str,
) -> None:
    """Encrypt and write an auth vault payload."""
    crypt = _import_vaultconfig_crypt()
    expanded = path.expanduser()

    plaintext = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    encrypted = crypt.encrypt(plaintext, password)

    # Warn if somehow encryption did not produce the expected header.
    _warn_if_not_encrypted(encrypted, expanded)

    _secure_write(expanded, encrypted)


def vault_profile_to_dict(profile: VaultProfile) -> dict[str, object]:
    """Convert a VaultProfile to a dict suitable for serialization."""
    return {
        "name": profile.name,
        "kind": profile.kind,
        **profile.data,
    }


def redacted_vault_dict(vault: AuthVault) -> dict[str, object]:
    """Return a redacted representation of the vault safe for logging/output."""
    profiles: dict[str, object] = {}
    for name, profile in vault.profiles.items():
        profiles[name] = {
            "kind": profile.kind,
            "fields": sorted(profile.data.keys()),
        }
    return {
        "version": vault.version,
        "source_path": str(vault.source_path),
        "profile_count": len(vault.profiles),
        "profiles": profiles,
    }


def redacted_profile_dict(profile: VaultProfile) -> dict[str, object]:
    """Return a redacted representation of a single vault profile."""
    return {
        "name": profile.name,
        "kind": profile.kind,
        "fields": sorted(profile.data.keys()),
    }
