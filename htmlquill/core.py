"""Public API for htmlquill — HTML to Markdown conversion."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from htmlquill.auth import (
    AuthStore,
    ResolvedAuth,
    auth_enabled_for_run,
    load_auth,
    redacted_auth_dict,
    resolve_auth,
    resolve_auth_path,
)
from htmlquill.clean import parse_and_clean
from htmlquill.config import (
    BrowserMode,
    CliOverrides,
    HtmlQuillConfig,
    ResolvedOptions,
    config_enabled_for_run,
    load_config,
    resolve_options,
)
from htmlquill.fetch import FetchError, fetch_html
from htmlquill.render import MarkdownRenderer, normalize_markdown


@dataclass(frozen=True)
class ResolvedFetchContext:
    options: ResolvedOptions
    auth: ResolvedAuth
    config_path: Path | None
    auth_path: Path | None


def html_to_markdown(
    html: str,
    *,
    base_url: str | None = None,
    title: str | None = None,
) -> str:
    """Convert an HTML document or fragment to Markdown."""

    root = parse_and_clean(html)
    renderer = MarkdownRenderer(base_url=base_url)
    markdown = renderer.render(root)
    if title:
        markdown = f"# {title}\n\n{markdown}"
    return normalize_markdown(markdown)


def _config_from_input(config: bool | str | Path) -> HtmlQuillConfig:
    if config is False:
        return HtmlQuillConfig(source_path=None)
    if isinstance(config, (str, Path)):
        return load_config(Path(config))
    if not config_enabled_for_run(no_config=False):
        return HtmlQuillConfig(source_path=None)
    return load_config(None)


def _auth_store_from_input(
    auth: bool | str | Path,
    *,
    config_obj: HtmlQuillConfig,
    requested_profile: str | None,
) -> tuple[AuthStore | None, Path | None]:
    if auth is False:
        return None, None

    if isinstance(auth, (str, Path)):
        auth_path = Path(auth)
    else:
        if not auth_enabled_for_run(no_auth=False):
            return None, None
        config_dir = (
            config_obj.source_path.parent
            if config_obj.source_path is not None
            else None
        )
        auth_path = resolve_auth_path(
            explicit_auth_path=None,
            config_auth_path=config_obj.auth_file,
            config_dir=config_dir,
        )

    if not auth_path.exists():
        if requested_profile:
            raise FetchError(
                "auth profile "
                f"{requested_profile!r} requested but auth file does not exist: "
                f"{auth_path}"
            )
        return None, auth_path

    return load_auth(auth_path), auth_path


def resolve_url_context(
    url: str,
    *,
    timeout: float | None = None,
    headers: Mapping[str, str] | None = None,
    browser: BrowserMode | None = None,
    config: bool | str | Path = True,
    auth: bool | str | Path = True,
    profile: str | None = None,
) -> ResolvedFetchContext:
    """Resolve effective URL fetch options from built-ins/config/env/CLI-like
    overrides."""

    user_agent_override = None
    if headers and "User-Agent" in headers:
        user_agent_override = headers["User-Agent"]

    cli = CliOverrides(
        browser=browser,
        timeout=timeout,
        user_agent=user_agent_override,
        profile=profile,
    )

    config_obj = _config_from_input(config)
    resolved = resolve_options(url, config_obj, cli)

    auth_store, auth_path = _auth_store_from_input(
        auth,
        config_obj=config_obj,
        requested_profile=resolved.auth_profile,
    )
    resolved_auth = resolve_auth(auth_store, profile_name=resolved.auth_profile)

    return ResolvedFetchContext(
        options=resolved,
        auth=resolved_auth,
        config_path=config_obj.source_path,
        auth_path=auth_path,
    )


def resolved_context_to_dict(
    context: ResolvedFetchContext,
    *,
    headers: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Convert resolved context into a printable dictionary."""

    merged_headers = dict(context.options.headers)
    if headers:
        merged_headers.update(headers)

    return {
        "config_path": str(context.config_path)
        if context.config_path is not None
        else None,
        "auth_path": str(context.auth_path) if context.auth_path is not None else None,
        "browser": context.options.browser,
        "timeout": context.options.timeout,
        "headers": merged_headers,
        "auth": redacted_auth_dict(context.auth),
        "challenge_markers": list(context.options.challenge_markers),
        "fail_on_challenge": context.options.fail_on_challenge,
        "fallback_on_challenge": context.options.fallback_on_challenge,
    }


def url_to_markdown(
    url: str,
    *,
    timeout: float | None = None,
    headers: Mapping[str, str] | None = None,
    browser: BrowserMode | None = None,
    config: bool | str | Path = True,
    auth: bool | str | Path = True,
    profile: str | None = None,
) -> str:
    """Fetch a URL and convert the response HTML to Markdown."""

    context = resolve_url_context(
        url,
        timeout=timeout,
        headers=headers,
        browser=browser,
        config=config,
        auth=auth,
        profile=profile,
    )

    merged_headers = dict(context.options.headers)
    if headers:
        merged_headers.update(headers)

    html = fetch_html(
        url,
        timeout=context.options.timeout,
        headers=merged_headers,
        browser=context.options.browser,
        cookies=context.auth.cookies,
        playwright_storage_state=context.auth.playwright_storage_state,
        chromium_user_data_dir=context.auth.chromium_user_data_dir,
        challenge_markers=list(context.options.challenge_markers),
        fallback_on_challenge=context.options.fallback_on_challenge,
        fail_on_challenge=context.options.fail_on_challenge,
    )
    return html_to_markdown(html, base_url=url)
