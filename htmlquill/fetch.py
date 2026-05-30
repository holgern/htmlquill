"""HTTP fetching utilities for htmlquill."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Mapping, Sequence
from typing import Any, Literal
from urllib.parse import urlparse

import requests
from requests.cookies import RequestsCookieJar, create_cookie

from htmlquill.challenge import (
    DEFAULT_CHALLENGE_MARKERS,
    ChallengePageError,
    assert_not_challenge_page,
)

DEFAULT_USER_AGENT = "htmlquill/0.1 (+https://github.com/holgern/htmlquill)"

BrowserMode = Literal["auto", "requests", "playwright", "chromium"]


class FetchError(RuntimeError):
    """Raised when a URL cannot be fetched as HTML."""


def _fetch_with_playwright(
    url: str,
    *,
    timeout: float = 20.0,
    storage_state: str | None = None,
) -> str:
    """Fetch a URL using Playwright headless Chromium."""

    try:
        from playwright.sync_api import (  # type: ignore[import-not-found]
            sync_playwright,
        )
    except ImportError as exc:
        msg = (
            "Playwright is required for browser-based fetching. "
            "Install it with: "
            "pip install htmlquill[browser] "
            "&& playwright install chromium"
        )
        raise FetchError(msg) from exc

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context_kwargs: dict[str, Any] = {}
            if storage_state:
                context_kwargs["storage_state"] = storage_state
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
            html = page.content()
            context.close()
            browser.close()
    except Exception as exc:
        raise FetchError(f"browser fetch failed for {url!r}: {exc}") from exc

    return str(html)


CHROMIUM_EXECUTABLES = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
)


def _find_chromium() -> str | None:
    """Search PATH for a Chromium-like executable."""

    for name in CHROMIUM_EXECUTABLES:
        found = shutil.which(name)
        if found:
            return found
    return None


def _fetch_with_chromium(
    url: str,
    *,
    timeout: float = 20.0,
    chromium_user_data_dir: str | None = None,
) -> str:
    """Fetch a URL using a system Chromium executable in headless mode."""

    executable = _find_chromium()
    if executable is None:
        names = ", ".join(CHROMIUM_EXECUTABLES)
        raise FetchError(f"Chromium executable not found on PATH; tried: {names}")

    cmd = [
        executable,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--dump-dom",
    ]
    if chromium_user_data_dir:
        cmd.append(f"--user-data-dir={chromium_user_data_dir}")
    cmd.append(url)

    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise FetchError(f"chromium fetch timed out for {url!r}") from exc
    except OSError as exc:
        raise FetchError(f"failed to run chromium for {url!r}: {exc}") from exc

    if completed.returncode != 0:
        fallback_cmd = [
            executable,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--dump-dom",
        ]
        if chromium_user_data_dir:
            fallback_cmd.append(f"--user-data-dir={chromium_user_data_dir}")
        fallback_cmd.append(url)
        try:
            completed = subprocess.run(
                fallback_cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise FetchError(f"chromium fallback timed out for {url!r}") from exc
        except OSError as exc:
            raise FetchError(f"chromium fallback failed for {url!r}: {exc}") from exc
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            raise FetchError(f"chromium fetch failed for {url!r}: {stderr}")

    html = completed.stdout
    if not _looks_like_html(html):
        raise FetchError(f"chromium result did not look like HTML: {url!r}")
    return html


def _looks_like_html(text: str, content_type: str = "") -> bool:
    """Check if the response looks like HTML."""

    if "html" in content_type.lower():
        return True
    return text.lstrip()[:1] == "<"


def _cookies_to_jar(cookies: Sequence[dict[str, object]]) -> RequestsCookieJar:
    jar = RequestsCookieJar()
    for cookie in cookies:
        name = str(cookie.get("name", ""))
        value = str(cookie.get("value", ""))
        if not name:
            continue
        domain_raw = cookie.get("domain")
        path_raw = cookie.get("path")
        secure_raw = cookie.get("secure")
        http_only_raw = cookie.get("httpOnly")

        domain = str(domain_raw) if isinstance(domain_raw, str) else ""
        path = str(path_raw) if isinstance(path_raw, str) else "/"
        secure = bool(secure_raw)
        rest: dict[str, Any] = {}
        if bool(http_only_raw):
            rest["HttpOnly"] = True

        jar.set_cookie(
            create_cookie(
                name=name,
                value=value,
                domain=domain,
                path=path,
                secure=secure,
                rest=rest,
            )
        )
    return jar


def _assert_not_challenge(
    html: str,
    *,
    url: str,
    challenge_markers: Sequence[str],
    fail_on_challenge: bool,
) -> None:
    if not fail_on_challenge:
        return
    try:
        assert_not_challenge_page(html, url=url, markers=challenge_markers)
    except ChallengePageError as exc:
        hint = _challenge_error_hint(url, html)
        if hint:
            raise FetchError(f"{exc} ({hint})") from exc
        raise FetchError(str(exc)) from exc


def _challenge_error_hint(url: str, html: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    lower = html.lower()
    if host in {"reddit.com", "www.reddit.com", "old.reddit.com", "m.reddit.com"}:
        if (
            "blocked by network security" in lower
            or "file a ticket below" in lower
            or "please try to login with your reddit account" in lower
        ):
            return (
                "received a Reddit network-security block page instead of content "
                "HTML; "
                "Reddit may block automated clients. Try browser mode with a "
                "logged-in browser profile, retry later, or save/export the page "
                "manually. HtmlQuill no longer provides a built-in Reddit "
                "API/OAuth adapter."
            )
    return None


def _try_browser_fallbacks(
    url: str,
    *,
    timeout: float,
    challenge_markers: Sequence[str],
    fail_on_challenge: bool,
    playwright_storage_state: str | None,
    chromium_user_data_dir: str | None,
) -> str | None:
    if _find_chromium() is not None:
        try:
            chromium_html = _fetch_with_chromium(
                url,
                timeout=timeout,
                chromium_user_data_dir=chromium_user_data_dir,
            )
            _assert_not_challenge(
                chromium_html,
                url=url,
                challenge_markers=challenge_markers,
                fail_on_challenge=fail_on_challenge,
            )
            return chromium_html
        except FetchError:
            pass

    try:
        pw_html = _fetch_with_playwright(
            url,
            timeout=timeout,
            storage_state=playwright_storage_state,
        )
        _assert_not_challenge(
            pw_html,
            url=url,
            challenge_markers=challenge_markers,
            fail_on_challenge=fail_on_challenge,
        )
        return pw_html
    except FetchError:
        return None


def fetch_html(
    url: str,
    *,
    timeout: float = 20.0,
    headers: Mapping[str, str] | None = None,
    browser: BrowserMode = "auto",
    cookies: list[dict[str, object]] | None = None,
    playwright_storage_state: str | None = None,
    chromium_user_data_dir: str | None = None,
    challenge_markers: list[str] | None = None,
    fallback_on_challenge: bool = True,
    fail_on_challenge: bool = True,
) -> str:
    """Fetch a URL and return the HTML content as a string."""

    markers: Sequence[str] = challenge_markers or DEFAULT_CHALLENGE_MARKERS

    if browser == "chromium":
        chromium_html = _fetch_with_chromium(
            url,
            timeout=timeout,
            chromium_user_data_dir=chromium_user_data_dir,
        )
        _assert_not_challenge(
            chromium_html,
            url=url,
            challenge_markers=markers,
            fail_on_challenge=fail_on_challenge,
        )
        return chromium_html

    if browser == "playwright":
        pw_html = _fetch_with_playwright(
            url,
            timeout=timeout,
            storage_state=playwright_storage_state,
        )
        if not _looks_like_html(pw_html):
            raise FetchError(f"browser result did not look like HTML: {url!r}")
        _assert_not_challenge(
            pw_html,
            url=url,
            challenge_markers=markers,
            fail_on_challenge=fail_on_challenge,
        )
        return pw_html

    request_headers: dict[str, str] = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        request_headers.update(headers)

    request_cookies: RequestsCookieJar | None = None
    if cookies:
        request_cookies = _cookies_to_jar(cookies)

    try:
        response = requests.get(
            url,
            headers=request_headers,
            timeout=timeout,
            cookies=request_cookies,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        if (
            browser == "auto"
            and isinstance(exc, requests.HTTPError)
            and exc.response is not None
            and exc.response.status_code == 403
        ):
            fallback_html = _try_browser_fallbacks(
                url,
                timeout=timeout,
                challenge_markers=markers,
                fail_on_challenge=fail_on_challenge,
                playwright_storage_state=playwright_storage_state,
                chromium_user_data_dir=chromium_user_data_dir,
            )
            if fallback_html is not None:
                return fallback_html
        raise FetchError(f"failed to fetch {url!r}: {exc}") from exc

    content_type = response.headers.get("content-type", "")
    if not _looks_like_html(response.text, content_type):
        raise FetchError(f"URL did not look like HTML: {url!r}")

    try:
        _assert_not_challenge(
            response.text,
            url=url,
            challenge_markers=markers,
            fail_on_challenge=fail_on_challenge,
        )
    except FetchError:
        if browser == "auto" and fallback_on_challenge:
            fallback_html = _try_browser_fallbacks(
                url,
                timeout=timeout,
                challenge_markers=markers,
                fail_on_challenge=fail_on_challenge,
                playwright_storage_state=playwright_storage_state,
                chromium_user_data_dir=chromium_user_data_dir,
            )
            if fallback_html is not None:
                return fallback_html
        raise

    return response.text
