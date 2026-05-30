"""Public API for htmlquill — HTML to Markdown conversion."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
    resolve_auth_vault_file_from_config,
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
    auth_vault_path: Path | None = None


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


def _resolve_auth_vault_for_profile(
    *,
    config_obj: HtmlQuillConfig,
    profile_name: str,
) -> tuple[ResolvedAuth, Path | None]:
    """Try to load the encrypted vault and resolve a bearer token from it.

    Returns (updated_resolved_auth, vault_path_or_None).
    If the vault is not available or does not contain the profile, returns
    ResolvedAuth with no vault changes.
    """
    config_dir = (
        config_obj.source_path.parent if config_obj.source_path is not None else None
    )
    vault_path = resolve_auth_vault_file_from_config(config_obj, config_dir=config_dir)
    if vault_path is None:
        vault_path = Path("~/.config/htmlquill/auth.vault").expanduser()
    if not vault_path.exists():
        return ResolvedAuth(profile_name=profile_name, token_source=None), vault_path

    try:
        from htmlquill.reddit_oauth import resolve_reddit_bearer_token
        from htmlquill.vault import load_auth_vault
    except ImportError:
        # vaultconfig not available
        return ResolvedAuth(profile_name=profile_name, token_source=None), vault_path

    try:
        vault = load_auth_vault(vault_path, prompt=True)
    except Exception:
        # Vault unavailable (wrong password, missing vaultconfig, etc.)
        return ResolvedAuth(profile_name=profile_name, token_source=None), vault_path

    if profile_name not in vault.profiles:
        return ResolvedAuth(profile_name=profile_name, token_source=None), vault_path

    profile = vault.profiles[profile_name]
    if profile.kind != "reddit_oauth":
        return ResolvedAuth(profile_name=profile_name, token_source=None), vault_path

    user_agent = "linux:htmlquill:v0.3.0"
    try:
        access_token, updated_data = resolve_reddit_bearer_token(
            profile.data,
            user_agent=user_agent,
            timeout=30.0,
        )
    except FetchError:
        # Token refresh failed
        return ResolvedAuth(profile_name=profile_name, token_source=None), vault_path

    # If the vault was updated (token refreshed), persist it.
    if updated_data is not None:
        try:
            from htmlquill.vault import get_vault_password, save_auth_vault

            # Use the same password we just used to decrypt.
            # We re-prompt since we don't cache passwords.
            password = get_vault_password("HtmlQuill vault password: ")
            vault_payload: dict[str, Any] = {
                "version": vault.version,
                "profiles": {},
            }
            for name, p in vault.profiles.items():
                if name == profile_name:
                    vault_payload["profiles"][name] = updated_data
                else:
                    vault_payload["profiles"][name] = {
                        "kind": p.kind,
                        **p.data,
                    }
            save_auth_vault(vault_path, vault_payload, password=password)
        except Exception:
            pass  # Non-fatal: token is still in memory for this run.

    return ResolvedAuth(
        profile_name=profile_name,
        bearer_token=access_token,
        token_source="vault",
    ), vault_path


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

    # If legacy auth didn't provide a bearer token and we have a requested
    # profile, try the encrypted vault.
    auth_vault_path: Path | None = None
    if (
        auth is not False
        and resolved.auth_profile
        and not resolved_auth.bearer_token
        and not resolved_auth.token_env
    ):
        vault_auth, auth_vault_path = _resolve_auth_vault_for_profile(
            config_obj=config_obj,
            profile_name=resolved.auth_profile,
        )
        if vault_auth.bearer_token:
            resolved_auth = vault_auth

    return ResolvedFetchContext(
        options=resolved,
        auth=resolved_auth,
        config_path=config_obj.source_path,
        auth_path=auth_path,
        auth_vault_path=auth_vault_path,
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
        "auth_vault_path": str(context.auth_vault_path)
        if context.auth_vault_path is not None
        else None,
        "browser": context.options.browser,
        "adapter": context.options.adapter,
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

    if context.options.adapter == "reddit_api":
        from htmlquill.adapters.reddit import (
            fetch_reddit_thread_json,
            parse_reddit_url,
            reddit_thread_json_to_markdown,
        )

        reddit_ref = parse_reddit_url(url)
        if reddit_ref is not None:
            # If the token came from the vault and needs refresh, it was
            # already refreshed in resolve_url_context. Pass through.
            payload = fetch_reddit_thread_json(
                url,
                options=context.options,
                auth=context.auth,
            )
            return reddit_thread_json_to_markdown(payload, source_url=url)

        host = (urlparse(url).hostname or "").lower()
        if host.endswith("reddit.com"):
            raise FetchError(
                "reddit_api adapter currently supports Reddit comments URLs only "
                "(.../r/<subreddit>/comments/<post_id>/...)"
            )

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
