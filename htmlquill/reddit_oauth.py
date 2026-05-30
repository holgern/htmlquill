"""Reddit OAuth helpers: authorization URL, code exchange, token refresh."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests

from htmlquill.fetch import FetchError

_REDDIT_AUTHORIZE_URL = "https://www.reddit.com/api/v1/authorize"
_REDDIT_ACCESS_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_REDDIT_REVOKE_TOKEN_URL = "https://www.reddit.com/api/v1/revoke_token"


@dataclass(frozen=True)
class RedditOAuthTokens:
    """Tokens returned by Reddit OAuth code exchange or token refresh."""

    access_token: str
    refresh_token: str | None
    expires_in: int | None
    scope: str
    token_type: str


def build_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    scope: str = "read",
    duration: str = "permanent",
) -> str:
    """Build the Reddit OAuth authorization URL."""
    params = {
        "client_id": client_id,
        "response_type": "code",
        "state": state,
        "redirect_uri": redirect_uri,
        "duration": duration,
        "scope": scope,
    }
    return f"{_REDDIT_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_tokens(
    *,
    client_id: str,
    client_secret: str | None,
    code: str,
    redirect_uri: str,
    user_agent: str,
    timeout: float,
) -> RedditOAuthTokens:
    """Exchange an authorization code for access/refresh tokens."""
    auth = (client_id, client_secret or "")
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }

    try:
        response = requests.post(
            _REDDIT_ACCESS_TOKEN_URL,
            auth=auth,
            data=data,
            headers=headers,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise FetchError(f"Reddit OAuth token exchange failed: {exc}") from exc

    if response.status_code != 200:
        raise FetchError(
            f"Reddit OAuth token exchange returned {response.status_code}: "
            f"{response.text[:200]}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise FetchError("Reddit OAuth token exchange returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise FetchError("Reddit OAuth token exchange returned unexpected payload")

    if "error" in payload:
        raise FetchError(
            f"Reddit OAuth error: {payload.get('error', 'unknown')}"
        )

    return RedditOAuthTokens(
        access_token=str(payload.get("access_token", "")),
        refresh_token=payload.get("refresh_token"),
        expires_in=payload.get("expires_in"),
        scope=str(payload.get("scope", "")),
        token_type=str(payload.get("token_type", "bearer")),
    )


def refresh_access_token(
    *,
    client_id: str,
    client_secret: str | None,
    refresh_token: str,
    user_agent: str,
    timeout: float,
) -> RedditOAuthTokens:
    """Refresh an access token using a refresh token."""
    auth = (client_id, client_secret or "")
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }

    try:
        response = requests.post(
            _REDDIT_ACCESS_TOKEN_URL,
            auth=auth,
            data=data,
            headers=headers,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise FetchError(f"Reddit OAuth token refresh failed: {exc}") from exc

    if response.status_code != 200:
        raise FetchError(
            f"Reddit OAuth token refresh returned {response.status_code}: "
            f"{response.text[:200]}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise FetchError("Reddit OAuth token refresh returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise FetchError("Reddit OAuth token refresh returned unexpected payload")

    if "error" in payload:
        raise FetchError(
            f"Reddit OAuth refresh error: {payload.get('error', 'unknown')}"
        )

    return RedditOAuthTokens(
        access_token=str(payload.get("access_token", "")),
        refresh_token=payload.get("refresh_token"),
        expires_in=payload.get("expires_in"),
        scope=str(payload.get("scope", "")),
        token_type=str(payload.get("token_type", "bearer")),
    )


def revoke_token(
    *,
    client_id: str,
    client_secret: str | None,
    token: str,
    token_type_hint: str = "access_token",
    user_agent: str,
    timeout: float,
) -> bool:
    """Revoke a Reddit OAuth token.

    Returns True if revocation succeeded or token was already invalid,
    raises FetchError on network/configuration errors.
    """
    auth = (client_id, client_secret or "")
    data = {
        "token": token,
        "token_type_hint": token_type_hint,
    }
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }

    try:
        response = requests.post(
            _REDDIT_REVOKE_TOKEN_URL,
            auth=auth,
            data=data,
            headers=headers,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise FetchError(f"Reddit OAuth token revocation failed: {exc}") from exc

    # 200 or 204 indicates success or token already invalid.
    return response.status_code in {200, 204}


def resolve_reddit_bearer_token(
    profile_data: dict[str, Any],
    *,
    user_agent: str,
    timeout: float,
) -> tuple[str, dict[str, Any] | None]:
    """Resolve a current Reddit bearer token from a vault profile.

    Returns (access_token, updated_profile_data_or_None).
    When the access token is still valid, returns it unchanged.
    When expired, refreshes and returns updated profile data.
    """
    access_token = profile_data.get("access_token")
    expires_at = profile_data.get("expires_at")
    refresh_token = profile_data.get("refresh_token")
    client_id = profile_data.get("client_id")
    client_secret = profile_data.get("client_secret")

    now = time.time()

    # If token exists and is not expired (60s buffer), return it.
    if (
        access_token
        and isinstance(access_token, str)
        and access_token.strip()
        and expires_at is not None
        and isinstance(expires_at, (int, float))
        and now < expires_at - 60
    ):
        return access_token, None

    # Need to refresh.
    if (
        not refresh_token
        or not isinstance(refresh_token, str)
        or not refresh_token.strip()
    ):
        raise FetchError(
            "Reddit OAuth access token expired and no refresh token is available. "
            "Run `htmlquill auth login reddit` to re-authenticate."
        )

    if not client_id or not isinstance(client_id, str) or not client_id.strip():
        raise FetchError(
            "Reddit OAuth client_id is missing from vault profile. "
            "Run `htmlquill auth login reddit` to re-authenticate."
        )

    tokens = refresh_access_token(
        client_id=client_id,
        client_secret=client_secret if isinstance(client_secret, str) else None,
        refresh_token=refresh_token,
        user_agent=user_agent,
        timeout=timeout,
    )

    # Build updated profile data.
    updated = dict(profile_data)
    updated["access_token"] = tokens.access_token
    if tokens.expires_in is not None:
        updated["expires_at"] = int(now + tokens.expires_in)
    updated["updated_at"] = int(now)
    if tokens.refresh_token:
        updated["refresh_token"] = tokens.refresh_token
    updated["scope"] = tokens.scope
    updated["token_type"] = tokens.token_type

    return tokens.access_token, updated
