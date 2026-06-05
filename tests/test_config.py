"""Tests for htmlquill.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from htmlquill.challenge import DEFAULT_CHALLENGE_MARKERS
from htmlquill.config import CliOverrides, load_config, resolve_options


def test_loads_default_config_when_file_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    cfg = load_config()
    assert cfg.defaults.timeout == 20.0
    assert cfg.defaults.browser == "auto"
    assert cfg.source_path is not None
    assert cfg.source_path.name == "config.toml"


def test_loads_config_from_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_home = tmp_path / "xdg"
    config_dir = config_home / "htmlquill"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    config_path.write_text(
        """
version = 1

[defaults]
timeout = 33
browser = "requests"
user_agent = "ConfigUA/1.0"

[sites."medium.com"]
browser = "chromium"
auth = "medium"
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    cfg = load_config()
    assert cfg.defaults.timeout == 33.0
    assert cfg.defaults.browser == "requests"


def test_htmlquill_config_env_overrides_default_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "custom.toml"
    config_path.write_text(
        """
version = 1
[defaults]
timeout = 77
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HTMLQUILL_CONFIG", str(config_path))

    cfg = load_config()
    assert cfg.defaults.timeout == 77.0
    assert cfg.source_path == config_path


def test_cli_overrides_config_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
version = 1
[defaults]
timeout = 30
browser = "requests"
user_agent = "ConfigUA/1.0"
""",
        encoding="utf-8",
    )

    cfg = load_config(config_path)
    opts = resolve_options(
        "https://example.com",
        cfg,
        CliOverrides(browser="chromium", timeout=5.0, user_agent="CliUA/2.0"),
    )

    assert opts.browser == "chromium"
    assert opts.timeout == 5.0
    assert opts.headers["User-Agent"] == "CliUA/2.0"


def test_site_specific_hostname_suffix_matching(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
version = 1
[defaults]
browser = "requests"

[sites."medium.com"]
browser = "chromium"
auth = "medium"
""",
        encoding="utf-8",
    )

    cfg = load_config(config_path)
    opts = resolve_options("https://alain-airom.medium.com/post", cfg, CliOverrides())
    assert opts.browser == "chromium"
    assert opts.auth_profile == "medium"


def test_invalid_browser_value_raises_clean_error(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        """
version = 1
[defaults]
browser = "netscape"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid browser value"):
        load_config(config_path)


def test_global_challenge_markers_extend_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
version = 1
[challenge]
markers = ["custom challenge marker"]
""",
        encoding="utf-8",
    )

    cfg = load_config(config_path)
    opts = resolve_options("https://example.com", cfg, CliOverrides())

    assert "custom challenge marker" in opts.challenge_markers
    for marker in DEFAULT_CHALLENGE_MARKERS:
        assert marker in opts.challenge_markers


def test_site_challenge_markers_extend_global_and_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
version = 1
[challenge]
markers = ["global marker"]

[sites."example.com"]
challenge_markers = ["site marker"]
""",
        encoding="utf-8",
    )

    cfg = load_config(config_path)
    opts = resolve_options("https://example.com/path", cfg, CliOverrides())

    assert "site marker" in opts.challenge_markers
    assert "global marker" in opts.challenge_markers
    for marker in DEFAULT_CHALLENGE_MARKERS:
        assert marker in opts.challenge_markers


def test_legacy_reddit_api_adapter_is_migrated_to_html(tmp_path: Path) -> None:
    config_path = tmp_path / "legacy.toml"
    config_path.write_text(
        """
version = 1
[sites."reddit.com"]
adapter = "reddit_api"
""",
        encoding="utf-8",
    )

    cfg = load_config(config_path)
    resolved = resolve_options(
        "https://www.reddit.com/r/test/comments/abc/title/",
        cfg,
        CliOverrides(),
    )

    assert resolved.adapter == "html"
    assert cfg.warnings == (
        "sites.reddit.com.adapter: adapter='reddit_api' was removed; "
        "using adapter='html'. Remove this setting from config.toml.",
    )


def test_unrelated_url_ignores_legacy_reddit_api_adapter(tmp_path: Path) -> None:
    config_path = tmp_path / "legacy.toml"
    config_path.write_text(
        """
version = 1
[sites."reddit.com"]
adapter = "reddit_api"

[sites."addyosmani.com"]
browser = "requests"
""",
        encoding="utf-8",
    )

    cfg = load_config(config_path)
    resolved = resolve_options(
        "https://addyosmani.com/blog/agent-skills/",
        cfg,
        CliOverrides(),
    )

    assert resolved.adapter == "html"
    assert resolved.browser == "requests"


def test_invalid_adapter_value_raises_clean_error(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        """
version = 1
[sites."reddit.com"]
adapter = "bad_adapter"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid adapter value"):
        load_config(config_path)


def test_reddit_url_returns_html_adapter_by_default(tmp_path: Path) -> None:
    cfg = load_config(None)
    opts = resolve_options(
        "https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/title/",
        cfg,
        CliOverrides(),
    )
    assert opts.adapter == "html"


def test_legacy_auth_vault_file_is_ignored_with_warning(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
version = 1
[paths]
auth_file = "auth.json"
auth_vault_file = "auth.vault"
""".strip(),
        encoding="utf-8",
    )

    cfg = load_config(config_path)

    assert cfg.auth_file == "auth.json"
    assert any("auth_vault_file" in warning for warning in cfg.warnings)

