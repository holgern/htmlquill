"""Unit tests for doctor diagnostics."""

from __future__ import annotations

import json

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
