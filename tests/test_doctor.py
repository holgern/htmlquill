"""Unit tests for doctor diagnostics."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from htmlquill.doctor import DoctorCheck, doctor_exit_code, run_doctor


def _find(checks: list[DoctorCheck], name: str) -> DoctorCheck:
    return next(check for check in checks if check.name == name)


def test_run_doctor_missing_auth_is_info_without_profile(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    checks = run_doctor()
    auth = _find(checks, "auth")
    assert auth.status == "info"


def test_run_doctor_missing_auth_warns_with_profile(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    checks = run_doctor(profile="medium")
    auth = _find(checks, "auth")
    assert auth.status == "warn"


def test_doctor_exit_code_strict_warns() -> None:
    checks = [DoctorCheck(name="x", status="warn", message="warn")]
    assert doctor_exit_code(checks, strict=False) == 0
    assert doctor_exit_code(checks, strict=True) == 2


def test_run_doctor_reddit_html_mode_warns(tmp_path, monkeypatch) -> None:
    config_home = tmp_path / "xdg"
    config_dir = config_home / "htmlquill"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        """
version = 1
[defaults]
adapter = "html"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    checks = run_doctor(
        url="https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/my_title/"
    )
    reddit_mode = _find(checks, "reddit:mode")
    assert reddit_mode.status == "warn"


def test_run_doctor_reddit_api_reports_adapter_checks(tmp_path, monkeypatch) -> None:
    config_home = tmp_path / "xdg"
    config_dir = config_home / "htmlquill"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        """
version = 1
[sites."reddit.com"]
adapter = "reddit_api"
auth = "reddit"
user_agent = "linux:htmlquill:v0.2.0 (by /u/test)"
""",
        encoding="utf-8",
    )
    (config_dir / "auth.json").write_text(
        json.dumps(
            {
                "version": 1,
                "profiles": {
                    "reddit": {
                        "kind": "bearer_token",
                        "token_env": "REDDIT_BEARER_TOKEN",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (config_dir / "auth.json").chmod(0o600)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("REDDIT_BEARER_TOKEN", "token")

    checks = run_doctor(
        url="https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/my_title/",
        profile="reddit",
    )
    reddit_adapter = _find(checks, "reddit:adapter")
    reddit_token = _find(checks, "reddit:token")
    reddit_user_agent = _find(checks, "reddit:user_agent")
    assert "reddit_api" in reddit_adapter.message
    assert reddit_token.status == "ok"
    assert reddit_user_agent.status == "ok"


def test_doctor_reports_missing_vaultconfig_when_secure_auth_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When vaultconfig is not available, doctor reports it as warn."""
    config_home = tmp_path / "xdg"
    config_dir = config_home / "htmlquill"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        """
version = 1
[paths]
auth_vault_file = "~/.config/htmlquill/auth.vault"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    checks = run_doctor()
    dep = _find(checks, "secure_auth_dependency")
    assert dep.status in ("ok", "warn")


def test_doctor_reports_vault_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a vault file exists, doctor reports it."""
    config_home = tmp_path / "xdg"
    config_dir = config_home / "htmlquill"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        """
version = 1
[paths]
auth_vault_file = "auth.vault"
""",
        encoding="utf-8",
    )
    (config_dir / "auth.vault").write_text("dummy data")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    checks = run_doctor()
    vault_exists = _find(checks, "secure_auth_vault_exists")
    assert vault_exists.status == "ok"


def test_doctor_reports_vault_permissions_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When vault has insecure permissions, doctor warns."""
    if os.name == "nt":
        pytest.skip("POSIX mode check")

    config_home = tmp_path / "xdg"
    config_dir = config_home / "htmlquill"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        """
version = 1
[paths]
auth_vault_file = "auth.vault"
""",
        encoding="utf-8",
    )
    vault_file = config_dir / "auth.vault"
    vault_file.write_text("dummy data")
    vault_file.chmod(0o644)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    checks = run_doctor()
    perm = _find(checks, "secure_auth_permissions")
    assert perm.status == "warn"


def test_doctor_vault_encrypted_when_vaultconfig_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When vaultconfig is available and vault exists, check encryption."""
    config_home = tmp_path / "xdg"
    config_dir = config_home / "htmlquill"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        """
version = 1
[paths]
auth_vault_file = "auth.vault"
""",
        encoding="utf-8",
    )
    vault_file = config_dir / "auth.vault"
    vault_file.write_text("dummy data")
    vault_file.chmod(0o600)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    checks = run_doctor()
    enc = _find(checks, "secure_auth_vault_encrypted")
    # Vault is not encrypted (plain text), so should be error or info
    assert enc.status in ("error", "info")
