"""Tests for htmlquill.reddit_oauth."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from htmlquill.fetch import FetchError
from htmlquill.reddit_oauth import (
    build_authorize_url,
    exchange_code_for_tokens,
    refresh_access_token,
    resolve_reddit_bearer_token,
    revoke_token,
)


class TestBuildAuthorizeUrl:
    def test_url_contains_expected_params(self) -> None:
        url = build_authorize_url(
            client_id="test-client",
            redirect_uri="http://127.0.0.1:8765/callback",
            state="random-state",
            scope="read",
            duration="permanent",
        )
        assert "client_id=test-client" in url
        assert "response_type=code" in url
        assert "state=random-state" in url
        assert "duration=permanent" in url
        assert "scope=read" in url
        assert url.startswith("https://www.reddit.com/api/v1/authorize?")


class TestExchangeCodeForTokens:
    def test_posts_expected_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict = {}

        def _mock_post(url, **kwargs):
            captured["url"] = url
            captured["data"] = kwargs.get("data", {})
            captured["auth"] = kwargs.get("auth")
            mock = MagicMock()
            mock.status_code = 200
            mock.json.return_value = {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
                "scope": "read",
                "token_type": "bearer",
            }
            return mock

        monkeypatch.setattr("requests.post", _mock_post)

        tokens = exchange_code_for_tokens(
            client_id="test-client",
            client_secret="test-secret",
            code="auth-code",
            redirect_uri="http://127.0.0.1:8765/callback",
            user_agent="test-agent",
            timeout=30.0,
        )

        assert tokens.access_token == "new-access"
        assert tokens.refresh_token == "new-refresh"
        assert tokens.expires_in == 3600
        assert captured["url"] == "https://www.reddit.com/api/v1/access_token"
        assert captured["data"]["grant_type"] == "authorization_code"
        assert captured["data"]["code"] == "auth-code"

    def test_handles_error_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock = MagicMock()
        mock.status_code = 400
        mock.text = '{"error": "invalid_grant"}'

        monkeypatch.setattr("requests.post", lambda *a, **kw: mock)

        with pytest.raises(FetchError, match="token exchange returned 400"):
            exchange_code_for_tokens(
                client_id="test-client",
                client_secret=None,
                code="bad-code",
                redirect_uri="http://127.0.0.1:8765/callback",
                user_agent="test-agent",
                timeout=30.0,
            )

    def test_handles_error_in_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {"error": "invalid_grant"}

        monkeypatch.setattr("requests.post", lambda *a, **kw: mock)

        with pytest.raises(FetchError, match="OAuth error: invalid_grant"):
            exchange_code_for_tokens(
                client_id="test-client",
                client_secret=None,
                code="bad-code",
                redirect_uri="http://127.0.0.1:8765/callback",
                user_agent="test-agent",
                timeout=30.0,
            )


class TestRefreshAccessToken:
    def test_posts_expected_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict = {}

        def _mock_post(url, **kwargs):
            captured["url"] = url
            captured["data"] = kwargs.get("data", {})
            mock = MagicMock()
            mock.status_code = 200
            mock.json.return_value = {
                "access_token": "refreshed-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
                "scope": "read",
                "token_type": "bearer",
            }
            return mock

        monkeypatch.setattr("requests.post", _mock_post)

        tokens = refresh_access_token(
            client_id="test-client",
            client_secret="test-secret",
            refresh_token="old-refresh",
            user_agent="test-agent",
            timeout=30.0,
        )

        assert tokens.access_token == "refreshed-access"
        assert tokens.refresh_token == "new-refresh"
        assert captured["data"]["grant_type"] == "refresh_token"
        assert captured["data"]["refresh_token"] == "old-refresh"

    def test_preserves_existing_refresh_when_response_omits_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {
            "access_token": "refreshed-access",
            "expires_in": 3600,
            "scope": "read",
            "token_type": "bearer",
        }

        monkeypatch.setattr("requests.post", lambda *a, **kw: mock)

        tokens = refresh_access_token(
            client_id="test-client",
            client_secret=None,
            refresh_token="old-refresh",
            user_agent="test-agent",
            timeout=30.0,
        )

        assert tokens.access_token == "refreshed-access"
        assert tokens.refresh_token is None  # Not returned by server


class TestResolveRedditBearerToken:
    def test_returns_valid_token_without_refresh(self) -> None:
        now = time.time()
        profile = {
            "access_token": "valid-token",
            "expires_at": now + 3600,
            "refresh_token": "refresh-tok",
            "client_id": "test-client",
        }
        token, updated = resolve_reddit_bearer_token(
            profile, user_agent="test-agent", timeout=30.0
        )
        assert token == "valid-token"
        assert updated is None

    def test_refreshes_expired_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {
            "access_token": "refreshed-token",
            "expires_in": 3600,
            "scope": "read",
            "token_type": "bearer",
        }
        monkeypatch.setattr("requests.post", lambda *a, **kw: mock)

        now = time.time()
        profile = {
            "access_token": "expired-token",
            "expires_at": now - 3600,
            "refresh_token": "refresh-tok",
            "client_id": "test-client",
        }
        token, updated = resolve_reddit_bearer_token(
            profile, user_agent="test-agent", timeout=30.0
        )
        assert token == "refreshed-token"
        assert updated is not None
        assert updated["access_token"] == "refreshed-token"

    def test_updates_refresh_token_when_response_includes_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {
            "access_token": "refreshed-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "scope": "read",
            "token_type": "bearer",
        }
        monkeypatch.setattr("requests.post", lambda *a, **kw: mock)

        now = time.time()
        profile = {
            "access_token": "expired-token",
            "expires_at": now - 3600,
            "refresh_token": "old-refresh-token",
            "client_id": "test-client",
        }
        token, updated = resolve_reddit_bearer_token(
            profile, user_agent="test-agent", timeout=30.0
        )
        assert updated is not None
        assert updated["refresh_token"] == "new-refresh-token"

    def test_errors_when_no_refresh_token(self) -> None:
        now = time.time()
        profile = {
            "access_token": "expired-token",
            "expires_at": now - 3600,
            "refresh_token": "",
            "client_id": "test-client",
        }
        with pytest.raises(FetchError, match="no refresh token"):
            resolve_reddit_bearer_token(profile, user_agent="test-agent", timeout=30.0)

    def test_no_tokens_logged_on_error(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify that token values do not appear in error messages or stdout."""
        mock = MagicMock()
        mock.status_code = 400
        monkeypatch.setattr("requests.post", lambda *a, **kw: mock)

        now = time.time()
        profile = {
            "access_token": "secret-token-abc123",
            "expires_at": now - 3600,
            "refresh_token": "secret-refresh-xyz789",
            "client_id": "test-client",
        }
        try:
            resolve_reddit_bearer_token(profile, user_agent="test-agent", timeout=30.0)
        except FetchError:
            pass

        captured = capsys.readouterr()
        assert "secret-token-abc123" not in captured.out
        assert "secret-token-abc123" not in captured.err
        assert "secret-refresh-xyz789" not in captured.out
        assert "secret-refresh-xyz789" not in captured.err


class TestRevokeToken:
    def test_revoke_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock = MagicMock()
        mock.status_code = 200

        monkeypatch.setattr("requests.post", lambda *a, **kw: mock)

        result = revoke_token(
            client_id="test-client",
            client_secret=None,
            token="tok-to-revoke",
            user_agent="test-agent",
            timeout=30.0,
        )
        assert result is True

    def test_revoke_204_also_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock = MagicMock()
        mock.status_code = 204

        monkeypatch.setattr("requests.post", lambda *a, **kw: mock)

        result = revoke_token(
            client_id="test-client",
            client_secret=None,
            token="tok-to-revoke",
            user_agent="test-agent",
            timeout=30.0,
        )
        assert result is True

    def test_revoke_network_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import requests as req

        def _raise(*a, **kw):
            raise req.ConnectionError("network down")

        monkeypatch.setattr("requests.post", _raise)

        with pytest.raises(FetchError, match="token revocation failed"):
            revoke_token(
                client_id="test-client",
                client_secret=None,
                token="tok-to-revoke",
                user_agent="test-agent",
                timeout=30.0,
            )
