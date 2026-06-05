"""Unit tests for doctor diagnostics."""

from __future__ import annotations

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


def test_run_doctor_reddit_url_has_no_reddit_specific_checks(
    tmp_path, monkeypatch
) -> None:
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
    names = {check.name for check in checks}
    assert not any(name.startswith("reddit:") for name in names)


def test_run_doctor_has_no_secure_auth_vault_checks(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    checks = run_doctor()
    assert not any(check.name.startswith("secure_auth_") for check in checks)
