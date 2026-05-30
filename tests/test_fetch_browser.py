"""Tests for browser fallback and challenge handling in htmlquill.fetch."""

from __future__ import annotations

import pytest

from htmlquill.fetch import FetchError, _fetch_with_playwright, fetch_html


class TestFetchWithPlaywrightImportError:
    def test_missing_playwright(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        for key in list(sys.modules):
            if key.startswith("playwright"):
                del sys.modules[key]

        monkeypatch.setitem(sys.modules, "playwright", None)
        monkeypatch.setitem(sys.modules, "playwright.sync_api", None)

        with pytest.raises(FetchError, match="Playwright is required"):
            _fetch_with_playwright("https://example.com")


class TestFetchHtmlRequestsMode:
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

    def test_requests_challenge_page_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            "<html><body>Performing security verification</body></html>"
        )
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_response)

        with pytest.raises(FetchError, match="security verification page"):
            fetch_html("https://example.com", browser="requests")

    def test_requests_reddit_wait_verification_page_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            "<html><head><title>Reddit - Please wait for verification</title></head>"
            '<body><form><input name="js_challenge" value="1"></form></body></html>'
        )
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_response)

        with pytest.raises(FetchError, match="security verification page"):
            fetch_html("https://www.reddit.com/r/test/comments/x/y", browser="requests")

    def test_requests_reddit_network_security_page_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
          <body>
            <h1>You've been blocked by network security.</h1>
            <p>
              If you think you've been blocked by mistake, file a ticket below
              and we'll look into it.
            </p>
          </body>
        </html>
        """
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_response)

        with pytest.raises(FetchError, match="Reddit network-security block page"):
            fetch_html(
                "https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/example/",
                browser="requests",
            )


class TestFetchHtmlAutoMode:
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

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status = MagicMock(
            side_effect=requests.HTTPError(response=mock_response)
        )
        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_response)

        monkeypatch.setattr("htmlquill.fetch._find_chromium", lambda: None)
        monkeypatch.setattr(
            "htmlquill.fetch._fetch_with_playwright",
            lambda url, *, timeout=20.0, storage_state=None: (
                "<html><body>PW</body></html>"
            ),
        )

        result = fetch_html("https://example.com", browser="auto")
        assert "PW" in result

    def test_auto_challenge_retries_chromium(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            "<html><body>Performing security verification</body></html>"
        )
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()
        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_response)

        monkeypatch.setattr(
            "htmlquill.fetch._find_chromium", lambda: "/usr/bin/chromium"
        )
        monkeypatch.setattr(
            "htmlquill.fetch._fetch_with_chromium",
            lambda url, *, timeout=20.0, chromium_user_data_dir=None: (
                "<html><body>Chromium fallback</body></html>"
            ),
        )

        result = fetch_html("https://example.com", browser="auto")
        assert "Chromium fallback" in result

    def test_auto_challenge_tries_playwright_after_chromium_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            "<html><body>Performing security verification</body></html>"
        )
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()
        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_response)

        monkeypatch.setattr(
            "htmlquill.fetch._find_chromium", lambda: "/usr/bin/chromium"
        )

        def _fail_chromium(
            url: str,
            *,
            timeout: float = 20.0,
            chromium_user_data_dir: str | None = None,
        ) -> str:
            raise FetchError("chromium failed")

        monkeypatch.setattr("htmlquill.fetch._fetch_with_chromium", _fail_chromium)
        monkeypatch.setattr(
            "htmlquill.fetch._fetch_with_playwright",
            lambda url, *, timeout=20.0, storage_state=None: (
                "<html><body>Playwright fallback</body></html>"
            ),
        )

        result = fetch_html("https://example.com", browser="auto")
        assert "Playwright fallback" in result

    def test_auto_challenge_all_fallbacks_fail_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            "<html><body>Performing security verification</body></html>"
        )
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()
        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_response)

        monkeypatch.setattr("htmlquill.fetch._find_chromium", lambda: None)

        def _fail_pw(
            url: str, *, timeout: float = 20.0, storage_state: str | None = None
        ) -> str:
            raise FetchError("Playwright missing")

        monkeypatch.setattr("htmlquill.fetch._fetch_with_playwright", _fail_pw)

        with pytest.raises(FetchError, match="security verification page"):
            fetch_html("https://example.com", browser="auto")


class TestFetchHtmlPlaywrightMode:
    def test_playwright_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "htmlquill.fetch._fetch_with_playwright",
            lambda url, *, timeout=20.0, storage_state=None: (
                "<html><body>PW result</body></html>"
            ),
        )

        result = fetch_html("https://example.com", browser="playwright")
        assert "PW result" in result

    def test_playwright_non_html_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "htmlquill.fetch._fetch_with_playwright",
            lambda url, *, timeout=20.0, storage_state=None: '{"json": "data"}',
        )

        with pytest.raises(FetchError, match="did not look like HTML"):
            fetch_html("https://example.com", browser="playwright")

    def test_playwright_passes_storage_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, str | None] = {}

        def _mock_pw(
            url: str,
            *,
            timeout: float = 20.0,
            storage_state: str | None = None,
        ) -> str:
            captured["storage_state"] = storage_state
            return "<html><body>PW result</body></html>"

        monkeypatch.setattr("htmlquill.fetch._fetch_with_playwright", _mock_pw)

        fetch_html(
            "https://example.com",
            browser="playwright",
            playwright_storage_state="/tmp/storage.json",
        )
        assert captured["storage_state"] == "/tmp/storage.json"


class TestFetchHtmlChromiumMode:
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

    def test_chromium_receives_user_data_dir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock

        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/chromium")
        captured: dict[str, list[str]] = {}

        def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
            captured["cmd"] = cmd
            completed = MagicMock()
            completed.returncode = 0
            completed.stdout = "<html><body>ok</body></html>"
            completed.stderr = ""
            return completed

        monkeypatch.setattr("subprocess.run", _run)

        fetch_html(
            "https://example.com",
            browser="chromium",
            chromium_user_data_dir="/tmp/htmlquill-profile",
        )

        assert any(
            part.startswith("--user-data-dir=/tmp/htmlquill-profile")
            for part in captured["cmd"]
        )
