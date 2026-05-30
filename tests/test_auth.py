"""Tests for htmlquill.auth and auth integration surfaces."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from htmlquill.auth import load_auth, redacted_auth_dict, resolve_auth
from htmlquill.core import resolve_url_context
from htmlquill.fetch import FetchError


def _write_auth(path: Path) -> None:
    path.write_text(
        """
{
  "version": 1,
  "profiles": {
    "medium": {
      "kind": "cookies",
      "cookies": [
        {
          "name": "sid",
          "value": "very-secret",
          "domain": ".medium.com",
          "path": "/",
          "secure": true,
          "httpOnly": true
        }
      ]
    }
  }
}
""",
        encoding="utf-8",
    )


def test_load_auth_json(tmp_path: Path) -> None:
    auth_file = tmp_path / "auth.json"
    _write_auth(auth_file)
    auth_file.chmod(0o600)

    store = load_auth(auth_file)
    assert "medium" in store.profiles
    profile = store.profiles["medium"]
    assert profile.kind == "cookies"
    assert len(profile.cookies) == 1


def test_missing_auth_file_non_fatal_when_no_profile_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_home = tmp_path / "cfg"
    (config_home / "htmlquill").mkdir(parents=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    context = resolve_url_context("https://example.com", config=False, auth=True)
    assert context.auth.profile_name is None


def test_missing_requested_profile_raises_useful_error(tmp_path: Path) -> None:
    auth_file = tmp_path / "auth.json"
    _write_auth(auth_file)
    auth_file.chmod(0o600)
    with pytest.raises(ValueError, match="auth profile 'missing' not found"):
        resolve_url_context(
            "https://example.com",
            config=False,
            auth=auth_file,
            profile="missing",
        )


def test_missing_auth_file_with_requested_profile_raises_fetch_error(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-auth.json"
    with pytest.raises(FetchError, match="auth profile 'medium' requested"):
        resolve_url_context(
            "https://medium.com/x",
            config=False,
            auth=missing,
            profile="medium",
        )


def test_posix_0644_permissions_raise_in_strict_mode(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("POSIX mode check")
    auth_file = tmp_path / "auth.json"
    _write_auth(auth_file)
    auth_file.chmod(0o644)

    with pytest.raises(PermissionError, match="group/world accessible"):
        load_auth(auth_file, strict_permissions=True)


def test_posix_0644_permissions_warn_in_non_strict_mode(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("POSIX mode check")
    auth_file = tmp_path / "auth.json"
    _write_auth(auth_file)
    auth_file.chmod(0o644)

    with pytest.warns(UserWarning, match="group/world accessible"):
        store = load_auth(auth_file, strict_permissions=False)
    assert "medium" in store.profiles


def test_auth_redaction_hides_cookie_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth_file = tmp_path / "auth.json"
    _write_auth(auth_file)
    auth_file.chmod(0o600)

    store = load_auth(auth_file)
    resolved = resolve_auth(store, profile_name="medium")
    redacted = redacted_auth_dict(resolved)

    assert redacted["cookies"] == "<redacted>"
    assert redacted["cookies_count"] == 1
    assert "very-secret" not in str(redacted)
