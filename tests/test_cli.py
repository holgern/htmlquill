"""Tests for htmlquill.cli — CLI behavior with monkeypatched fetch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from htmlquill.cli import main


class TestCLIStdout:
    def test_html_file_to_stdout(self, tmp_path: Path, capsys: object) -> None:

        html_file = tmp_path / "test.html"
        html_file.write_text(
            "<html><body><main><h1>Hello</h1><p>World</p></main></body></html>",
            encoding="utf-8",
        )
        rc = main([str(html_file)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "# Hello" in captured.out
        assert "World" in captured.out

    def test_stdin_to_stdout(self, capsys: object) -> None:
        import sys
        from io import StringIO

        html = "<main><p>Stdin test</p></main>"
        with patch.object(sys, "stdin", StringIO(html)):
            rc = main(["-"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Stdin test" in captured.out


class TestCLIOutputFile:
    def test_html_file_to_output(self, tmp_path: Path) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text(
            "<html><body><main><h1>Hello</h1><p>World</p></main></body></html>",
            encoding="utf-8",
        )
        output_file = tmp_path / "test.md"
        rc = main([str(html_file), "-o", str(output_file)])
        assert rc == 0
        md = output_file.read_text(encoding="utf-8")
        assert "# Hello" in md
        assert "World" in md


class TestCLIUrl:
    def test_url_mode(self, tmp_path: Path) -> None:
        output_file = tmp_path / "test.md"
        with patch("htmlquill.cli.url_to_markdown") as mock_url:
            mock_url.return_value = "# Fetched\n\nContent.\n"
            rc = main(["https://example.com", "-o", str(output_file)])
        assert rc == 0
        mock_url.assert_called_once()
        md = output_file.read_text(encoding="utf-8")
        assert "# Fetched" in md

    def test_url_with_timeout(self, tmp_path: Path) -> None:
        output_file = tmp_path / "test.md"
        with patch("htmlquill.cli.url_to_markdown") as mock_url:
            mock_url.return_value = "Content.\n"
            rc = main(["https://example.com", "--timeout", "5", "-o", str(output_file)])
        assert rc == 0
        assert mock_url.call_args[1]["timeout"] == 5.0

    def test_url_with_user_agent(self, tmp_path: Path) -> None:
        output_file = tmp_path / "test.md"
        with patch("htmlquill.cli.url_to_markdown") as mock_url:
            mock_url.return_value = "Content.\n"
            rc = main(
                [
                    "https://example.com",
                    "--user-agent",
                    "TestAgent/1.0",
                    "-o",
                    str(output_file),
                ]
            )
        assert rc == 0
        assert mock_url.call_args[1]["headers"] == {"User-Agent": "TestAgent/1.0"}

    def test_url_with_chromium_browser(self, tmp_path: Path) -> None:
        output_file = tmp_path / "test.md"
        with patch("htmlquill.cli.url_to_markdown") as mock_url:
            mock_url.return_value = "Content.\n"
            rc = main(
                [
                    "https://example.com",
                    "--browser",
                    "chromium",
                    "-o",
                    str(output_file),
                ]
            )
        assert rc == 0
        assert mock_url.call_args[1]["browser"] == "chromium"


class TestCLIError:
    def test_nonexistent_file(self) -> None:
        rc = main(["/nonexistent/path.html"])
        assert rc == 1

    def test_url_fetch_error(self, tmp_path: Path) -> None:
        from htmlquill.fetch import FetchError

        with patch("htmlquill.cli.url_to_markdown") as mock_url:
            mock_url.side_effect = FetchError("failed to fetch 'https://bad.url': 404")
            rc = main(["https://bad.url"])
        assert rc == 1
