"""Tests for htmlquill.cli."""

from __future__ import annotations

import json
import os
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from htmlquill.cli import app, main

runner = CliRunner()


class TestCLIConvertCompatibility:
    def test_html_file_auto_filename_from_heading(
        self, tmp_path: Path, monkeypatch: object
    ) -> None:
        monkeypatch.chdir(tmp_path)
        html_file = tmp_path / "test.html"
        html_file.write_text(
            "<html><body><main><h1>Hello</h1><p>World</p></main></body></html>",
            encoding="utf-8",
        )

        rc = main([str(html_file)])

        assert rc == 0
        output = tmp_path / "hello.md"
        assert output.exists()
        assert "# Hello" in output.read_text(encoding="utf-8")

    def test_stdin_to_stdout(self, capsys: object) -> None:
        import sys

        html = "<main><p>Stdin test</p></main>"
        with patch.object(sys, "stdin", StringIO(html)):
            rc = main(["-", "--stdout"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Stdin test" in captured.out

    def test_legacy_url_injects_convert(self, tmp_path: Path) -> None:
        output_file = tmp_path / "out.md"
        with patch("htmlquill.commands.convert.url_to_markdown") as mock_url:
            mock_url.return_value = "# Fetched\n\nContent\n"
            rc = main(["https://example.com", "-o", str(output_file)])
        assert rc == 0
        mock_url.assert_called_once()

    def test_explicit_convert_url(self, tmp_path: Path) -> None:
        output_file = tmp_path / "out.md"
        with patch("htmlquill.commands.convert.url_to_markdown") as mock_url:
            mock_url.return_value = "# Fetched\n\nContent\n"
            rc = main(["convert", "https://example.com", "-o", str(output_file)])
        assert rc == 0
        mock_url.assert_called_once()

    def test_url_with_timeout(self, tmp_path: Path) -> None:
        with patch("htmlquill.commands.convert.url_to_markdown") as mock_url:
            mock_url.return_value = "Content\n"
            rc = main(
                [
                    "https://example.com",
                    "--timeout",
                    "5",
                    "--stdout",
                ]
            )
        assert rc == 0
        assert mock_url.call_args[1]["timeout"] == 5.0

    def test_url_with_user_agent(self, tmp_path: Path) -> None:
        with patch("htmlquill.commands.convert.url_to_markdown") as mock_url:
            mock_url.return_value = "Content\n"
            rc = main(
                [
                    "https://example.com",
                    "--user-agent",
                    "TestAgent/1.0",
                    "--stdout",
                ]
            )
        assert rc == 0
        assert mock_url.call_args[1]["headers"] == {"User-Agent": "TestAgent/1.0"}

    def test_url_with_chromium_browser(self, tmp_path: Path) -> None:
        with patch("htmlquill.commands.convert.url_to_markdown") as mock_url:
            mock_url.return_value = "Content\n"
            rc = main(
                [
                    "https://example.com",
                    "--browser",
                    "chromium",
                    "--stdout",
                ]
            )
        assert rc == 0
        assert mock_url.call_args[1]["browser"] == "chromium"

    def test_print_config_reads_config_file(
        self, tmp_path: Path, monkeypatch: object, capsys: object
    ) -> None:
        config_home = tmp_path / "xdg"
        config_dir = config_home / "htmlquill"
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").write_text(
            """
version = 1
[defaults]
timeout = 41
browser = "requests"
""",
            encoding="utf-8",
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

        rc = main(["--print-config", "https://example.com"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["timeout"] == 41.0
        assert payload["browser"] == "requests"

    def test_no_config_ignores_toml(
        self, tmp_path: Path, monkeypatch: object, capsys: object
    ) -> None:
        config_home = tmp_path / "xdg"
        config_dir = config_home / "htmlquill"
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").write_text(
            """
version = 1
[defaults]
timeout = 99
browser = "chromium"
""",
            encoding="utf-8",
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

        rc = main(["--print-config", "--no-config", "https://example.com"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["timeout"] == 20.0
        assert payload["browser"] == "auto"

    def test_auth_file_and_profile_show_redacted(
        self, tmp_path: Path, capsys: object
    ) -> None:
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(
            """
{
  "version": 1,
  "profiles": {
    "medium": {
      "kind": "cookies",
      "cookies": [
        {"name": "sid", "value": "secret", "domain": ".medium.com"}
      ]
    }
  }
}
""",
            encoding="utf-8",
        )
        auth_file.chmod(0o600)

        rc = main(
            [
                "--print-config",
                "--auth-file",
                str(auth_file),
                "--profile",
                "medium",
                "https://medium.com/x",
            ]
        )
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["auth"]["profile"] == "medium"
        assert payload["auth"]["cookies"] == "<redacted>"
        assert payload["auth"]["cookies_count"] == 1

    def test_stdout_prints_without_saving(
        self, tmp_path: Path, capsys: object, monkeypatch: object
    ) -> None:
        monkeypatch.chdir(tmp_path)
        html_file = tmp_path / "test.html"
        html_file.write_text(
            "<main><h1>Hello</h1><p>World</p></main>", encoding="utf-8"
        )

        rc = main([str(html_file), "--stdout"])

        assert rc == 0
        captured = capsys.readouterr()
        assert "# Hello" in captured.out
        assert not (tmp_path / "hello.md").exists()

    def test_manual_output_still_writes_exact_path(
        self, tmp_path: Path,
    ) -> None:
        html_file = tmp_path / "test.html"
        manual = tmp_path / "custom.name"
        html_file.write_text(
            "<main><h1>Hello</h1><p>World</p></main>", encoding="utf-8"
        )

        rc = main([str(html_file), "-o", str(manual)])

        assert rc == 0
        assert manual.exists()

    def test_filename_only_prints_without_saving(
        self, tmp_path: Path, capsys: object, monkeypatch: object
    ) -> None:
        monkeypatch.chdir(tmp_path)
        html_file = tmp_path / "test.html"
        html_file.write_text(
            "<main><h1>Hello World</h1></main>", encoding="utf-8"
        )

        rc = main([str(html_file), "--filename-only"])

        assert rc == 0
        assert capsys.readouterr().out.strip() == str(tmp_path / "hello-world.md")
        assert not (tmp_path / "hello-world.md").exists()

    def test_generated_filename_collision_suffix(
        self, tmp_path: Path, monkeypatch: object
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "hello.md").write_text("old", encoding="utf-8")
        html_file = tmp_path / "test.html"
        html_file.write_text(
            "<main><h1>Hello</h1></main>", encoding="utf-8"
        )

        rc = main([str(html_file)])

        assert rc == 0
        assert (tmp_path / "hello-2.md").exists()

    def test_url_auto_filename_uses_fetched_heading(
        self, tmp_path: Path, monkeypatch: object
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with patch("htmlquill.commands.convert.url_to_markdown") as mock_url:
            mock_url.return_value = "# Fetched Title\n\nContent\n"
            rc = main(["https://example.com/article"])

        assert rc == 0
        assert (tmp_path / "fetched-title.md").exists()

    def test_output_dir_creates_directory(
        self, tmp_path: Path, monkeypatch: object
    ) -> None:
        monkeypatch.chdir(tmp_path)
        html_file = tmp_path / "test.html"
        html_file.write_text(
            "<main><h1>Title</h1></main>", encoding="utf-8"
        )

        rc = main([str(html_file), "--output-dir", str(tmp_path / "notes")])

        assert rc == 0
        assert (tmp_path / "notes" / "title.md").exists()

    def test_force_overwrites_generated_target(
        self, tmp_path: Path, monkeypatch: object
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "hello.md").write_text("old", encoding="utf-8")
        html_file = tmp_path / "test.html"
        html_file.write_text(
            "<main><h1>Hello</h1></main>", encoding="utf-8"
        )

        rc = main([str(html_file), "--force"])

        assert rc == 0
        content = (tmp_path / "hello.md").read_text(encoding="utf-8")
        assert "# Hello" in content


class TestTyperCommands:
    def test_help_lists_commands(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "convert" in result.output
        assert "config" in result.output
        assert "auth" in result.output
        assert "doctor" in result.output
        assert "analyse" in result.output
        assert "analyze" in result.output
        assert "preview" in result.output

    def test_config_path_prints_default(
        self, monkeypatch: object, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        result = runner.invoke(app, ["config", "path", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["config_path"].endswith("htmlquill/config.toml")

    def test_config_show_matches_old_print_config(
        self, monkeypatch: object, tmp_path: Path, capsys: object
    ) -> None:
        config_home = tmp_path / "xdg"
        config_dir = config_home / "htmlquill"
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").write_text(
            """
version = 1
[defaults]
timeout = 41
browser = "requests"
""",
            encoding="utf-8",
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

        rc = main(["--print-config", "https://example.com"])
        assert rc == 0
        legacy_payload = json.loads(capsys.readouterr().out)

        result = runner.invoke(
            app,
            ["config", "show", "https://example.com", "--json"],
        )
        assert result.exit_code == 0
        new_payload = json.loads(result.output)

        for key in ("browser", "timeout", "headers", "auth", "challenge_markers"):
            assert new_payload[key] == legacy_payload[key]

    def test_config_show_reddit_url_includes_adapter(
        self, monkeypatch: object, tmp_path: Path
    ) -> None:
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
        auth_path = config_dir / "auth.json"
        auth_path.write_text(
            """
{
  "version": 1,
  "profiles": {
    "reddit": {"kind": "bearer_token", "token_env": "REDDIT_BEARER_TOKEN"}
  }
}
""",
            encoding="utf-8",
        )
        auth_path.chmod(0o600)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

        result = runner.invoke(
            app,
            [
                "config",
                "show",
                "https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/my_title/",
                "--json",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["adapter"] == "reddit_api"

    def test_convert_reddit_uses_adapter_when_configured(
        self, monkeypatch: object, tmp_path: Path
    ) -> None:
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
        auth_path = config_dir / "auth.json"
        auth_path.write_text(
            """
{
  "version": 1,
  "profiles": {
    "reddit": {"kind": "bearer_token", "token_env": "REDDIT_BEARER_TOKEN"}
  }
}
""",
            encoding="utf-8",
        )
        auth_path.chmod(0o600)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
        monkeypatch.setenv("REDDIT_BEARER_TOKEN", "token-value")

        with patch("htmlquill.adapters.reddit.fetch_reddit_thread_json") as mock_fetch:
            with patch(
                "htmlquill.adapters.reddit.reddit_thread_json_to_markdown"
            ) as mock_render:
                mock_fetch.return_value = [
                    {"data": {"children": [{"data": {"title": "x"}}]}},
                    {"data": {"children": []}},
                ]
                mock_render.return_value = "# Title\n\nBody\n"
                result = runner.invoke(
                    app,
                    [
                        "convert",
                        "https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/my_title/",
                    ],
                )

        assert result.exit_code == 0
        assert "# Title" in result.output
        mock_fetch.assert_called_once()
        mock_render.assert_called_once()

    def test_config_init_writes_file_with_no_overwrite(
        self, tmp_path: Path, monkeypatch: object
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

        first = runner.invoke(app, ["config", "init"])
        assert first.exit_code == 0

        second = runner.invoke(app, ["config", "init"])
        assert second.exit_code != 0
        assert "already exists" in (second.output or str(second.exception))

        forced = runner.invoke(app, ["config", "init", "--force"])
        assert forced.exit_code == 0

    def test_auth_init_sets_0600_on_posix(
        self, tmp_path: Path, monkeypatch: object
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

        result = runner.invoke(app, ["auth", "init"])
        assert result.exit_code == 0

        auth_path = tmp_path / "xdg" / "htmlquill" / "auth.json"
        assert auth_path.exists()
        if os.name != "nt":
            assert (auth_path.stat().st_mode & 0o777) == 0o600

    def test_doctor_json_has_checks(self) -> None:
        result = runner.invoke(app, ["doctor", "--json"])
        assert result.exit_code in {0, 2}
        payload = json.loads(result.output)
        names = {check["name"] for check in payload["checks"]}
        assert "python" in names
        assert "import:typer" in names

    def test_analyse_markdown_counts_links_images_code(self, tmp_path: Path) -> None:
        md = tmp_path / "sample.md"
        md.write_text(
            "# Title\n\n"
            "[link](https://example.com)\n"
            "![img](img.png)\n"
            "`inline`\n\n"
            "```\nprint('x')\n```\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["analyse", str(md), "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["images"] == 1
        assert payload["links"] == 1
        assert payload["code_blocks"] == 1

    def test_analyse_html_converts_then_counts(self, tmp_path: Path) -> None:
        html = tmp_path / "sample.html"
        html.write_text(
            "<html><body><article><h1>Title</h1><p>Hello world</p></article>"
            "</body></html>",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["analyse", str(html), "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["headings"] >= 1
        assert payload["words"] >= 2

    def test_preview_plain_works_without_rich(self, tmp_path: Path) -> None:
        md = tmp_path / "preview.md"
        md.write_text("# Title\n\nHello preview\n", encoding="utf-8")

        result = runner.invoke(app, ["preview", str(md), "--plain"])
        assert result.exit_code == 0
        assert "Hello preview" in result.output




class TestMutualExclusion:
    def test_stdout_and_output_are_mutually_exclusive(
        self, tmp_path: Path
    ) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text(
            "<main><h1>Hello</h1></main>", encoding="utf-8"
        )
        rc = main([str(html_file), "--stdout", "-o", str(tmp_path / "x.md")])
        assert rc != 0

    def test_filename_only_and_stdout_are_mutually_exclusive(
        self, tmp_path: Path
    ) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text(
            "<main><h1>Hello</h1></main>", encoding="utf-8"
        )
        rc = main([str(html_file), "--stdout", "--filename-only"])
        assert rc != 0

    def test_output_dir_and_output_are_mutually_exclusive(
        self, tmp_path: Path
    ) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text(
            "<main><h1>Hello</h1></main>", encoding="utf-8"
        )
        rc = main([str(html_file), "--output-dir", "dir", "-o", "x.md"])
        assert rc != 0
class TestCLIError:
    def test_nonexistent_file(self) -> None:
        rc = main(["/nonexistent/path.html"])
        assert rc == 1

    def test_url_fetch_error(self) -> None:
        from htmlquill.fetch import FetchError

        with patch("htmlquill.commands.convert.url_to_markdown") as mock_url:
            mock_url.side_effect = FetchError("failed to fetch 'https://bad.url': 404")
            rc = main(["https://bad.url"])
        assert rc == 1
