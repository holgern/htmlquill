"""Tests for browser fallback logic in htmlquill.fetch."""

from __future__ import annotations

import pytest

from htmlquill.fetch import FetchError, _fetch_with_playwright, fetch_html


class TestFetchWithPlaywrightImportError:
    """When playwright is not installed, _fetch_with_playwright raises FetchError."""

    def test_missing_playwright(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Simulate playwright not being installed
        import sys

        # Remove playwright from sys.modules if present
        removed: list[str] = []
        for key in list(sys.modules):
            if key.startswith("playwright"):
                removed.append(key)
                del sys.modules[key]

        monkeypatch.setitem(sys.modules, "playwright", None)
        monkeypatch.setitem(sys.modules, "playwright.sync_api", None)

        with pytest.raises(FetchError, match="Playwright is required"):
            _fetch_with_playwright("https://example.com")


class TestFetchHtmlRequestsMode:
    """browser='requests' behaves like the original fetch_html."""

    def test_requests_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Hello</body></html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_response)

        result = fetch_html("https://example.com", browser="requests")
        assert "Hello" in result

    def test_requests_403_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import MagicMock

        import requests

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status = MagicMock(
            side_effect=requests.HTTPError(response=mock_response)
        )

        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_response)

        with pytest.raises(FetchError, match="failed to fetch"):
            fetch_html("https://example.com", browser="requests")


class TestFetchHtmlAutoMode:
    """browser='auto' tries requests first, falls back to playwright on 403."""

    def test_auto_requests_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Direct</body></html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_response)

        result = fetch_html("https://example.com", browser="auto")
        assert "Direct" in result

    def test_auto_fallback_on_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import MagicMock

        import requests

        # requests.get returns 403
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status = MagicMock(
            side_effect=requests.HTTPError(response=mock_response)
        )
        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_response)

        # _fetch_with_playwright returns valid HTML
        monkeypatch.setattr(
            "htmlquill.fetch._fetch_with_playwright",
            lambda url, *, timeout=20.0: "<html><body>Playwright content</body></html>",
        )

        result = fetch_html("https://example.com", browser="auto")
        assert "Playwright content" in result

    def test_auto_403_no_playwright_raises_original(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock

        import requests

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status = MagicMock(
            side_effect=requests.HTTPError(response=mock_response)
        )
        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_response)

        # Simulate playwright not available
        def _fail_pw(url: str, *, timeout: float = 20.0) -> str:
            raise FetchError("Playwright is required for browser-based fetching.")

        monkeypatch.setattr("htmlquill.fetch._fetch_with_playwright", _fail_pw)

        with pytest.raises(FetchError, match="failed to fetch"):
            fetch_html("https://example.com", browser="auto")


class TestFetchHtmlPlaywrightMode:
    """browser='playwright' always uses the browser backend."""

    def test_playwright_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "htmlquill.fetch._fetch_with_playwright",
            lambda url, *, timeout=20.0: "<html><body>PW result</body></html>",
        )

        result = fetch_html("https://example.com", browser="playwright")
        assert "PW result" in result

    def test_playwright_non_html_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "htmlquill.fetch._fetch_with_playwright",
            lambda url, *, timeout=20.0: '{"json": "data"}',
        )

        with pytest.raises(FetchError, match="did not look like HTML"):
            fetch_html("https://example.com", browser="playwright")


class TestLooksLikeHtml:
    """Test the _looks_like_html helper."""

    def test_html_content_type(self) -> None:
        from htmlquill.fetch import _looks_like_html

        assert _looks_like_html("anything", "text/html") is True

    def test_html_prefix(self) -> None:
        from htmlquill.fetch import _looks_like_html

        assert _looks_like_html("<html>hello</html>") is True

    def test_non_html(self) -> None:
        from htmlquill.fetch import _looks_like_html

        assert _looks_like_html('{"key": "value"}', "application/json") is False


class TestFetchHtmlChromiumMode:
    """browser='chromium' uses a system Chromium subprocess."""

    def test_chromium_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda name: None)
        with pytest.raises(FetchError, match="Chromium executable not found"):
            fetch_html("https://example.com", browser="chromium")

    def test_chromium_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import MagicMock

        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/chromium")

        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = "<html><body>Chromium content</body></html>"
        completed.stderr = ""

        monkeypatch.setattr("subprocess.run", lambda *a, **kw: completed)

        result = fetch_html("https://example.com", browser="chromium")
        assert "Chromium content" in result

    def test_chromium_non_html(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import MagicMock

        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/chromium")

        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = "not html"
        completed.stderr = ""

        monkeypatch.setattr("subprocess.run", lambda *a, **kw: completed)

        with pytest.raises(FetchError, match="did not look like HTML"):
            fetch_html("https://example.com", browser="chromium")

    def test_chromium_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import subprocess

        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/chromium")

        def _timeout(*a: object, **kw: object) -> None:
            raise subprocess.TimeoutExpired(cmd=["chromium"], timeout=20)

        monkeypatch.setattr("subprocess.run", _timeout)

        with pytest.raises(FetchError, match="chromium fetch timed out"):
            fetch_html("https://example.com", browser="chromium")

    def test_chromium_nonzero_exit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import MagicMock

        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/chromium")

        # Both --headless=new and legacy --headless fail
        failed = MagicMock()
        failed.returncode = 1
        failed.stdout = ""
        failed.stderr = "Error: something went wrong"

        monkeypatch.setattr("subprocess.run", lambda *a, **kw: failed)

        with pytest.raises(FetchError, match="chromium fetch failed"):
            fetch_html("https://example.com", browser="chromium")

    def test_chromium_legacy_headless_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock

        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/chromium")

        failed_new = MagicMock()
        failed_new.returncode = 1
        failed_new.stdout = ""
        failed_new.stderr = "Error: unknown flag"

        success_legacy = MagicMock()
        success_legacy.returncode = 0
        success_legacy.stdout = "<html><body>Legacy content</body></html>"
        success_legacy.stderr = ""

        call_count = 0

        def _run(*a: object, **kw: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return failed_new
            return success_legacy

        monkeypatch.setattr("subprocess.run", _run)

        result = fetch_html("https://example.com", browser="chromium")
        assert "Legacy content" in result
