"""Unit tests for doctor diagnostics."""

from __future__ import annotations

from htmlquill.doctor import DoctorCheck, doctor_exit_code, run_doctor


def _find(checks: list[DoctorCheck], name: str) -> DoctorCheck:
    return next(check for check in checks if check.name == name)


def test_run_doctor_missing_auth_is_info_without_profile(
    tmp_path, monkeypatch
) -> None:
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
