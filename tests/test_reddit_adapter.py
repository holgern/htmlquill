"""Tests for htmlquill.adapters.reddit."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from htmlquill.adapters.reddit import (
    fetch_reddit_thread_json,
    parse_reddit_url,
    reddit_thread_json_to_markdown,
)
from htmlquill.auth import ResolvedAuth
from htmlquill.config import ResolvedOptions
from htmlquill.fetch import FetchError


def _options(
    user_agent: str = "linux:htmlquill:v0.2.0 (by /u/test)",
) -> ResolvedOptions:
    return ResolvedOptions(
        adapter="reddit_api",
        browser="requests",
        timeout=20.0,
        headers={"User-Agent": user_agent},
        auth_profile="reddit",
        challenge_markers=(),
        fail_on_challenge=True,
        fallback_on_challenge=True,
    )


def _auth(token_env: str | None = "REDDIT_BEARER_TOKEN") -> ResolvedAuth:
    return ResolvedAuth(profile_name="reddit", token_env=token_env)


def test_parse_reddit_url_supported_variants() -> None:
    assert parse_reddit_url(
        "https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/my_title/"
    )
    assert parse_reddit_url(
        "https://old.reddit.com/r/ObsidianMD/comments/1q2b6fp/my_title/"
    )
    assert parse_reddit_url("https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/")


def test_parse_reddit_url_non_comment_path_returns_none() -> None:
    assert parse_reddit_url("https://www.reddit.com/r/ObsidianMD/") is None


def test_fetch_reddit_thread_json_adds_auth_and_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value=[
            {"data": {"children": [{"data": {"title": "x"}}]}},
            {"data": {"children": []}},
        ]
    )

    def _mock_get(url: str, **kwargs: object) -> MagicMock:
        captured["url"] = url
        captured.update(kwargs)
        return mock_response

    monkeypatch.setenv("REDDIT_BEARER_TOKEN", "token-value")
    monkeypatch.setattr("requests.get", _mock_get)

    payload = fetch_reddit_thread_json(
        "https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/my_title/",
        options=_options(),
        auth=_auth(),
    )
    assert isinstance(payload, list)
    assert captured["params"] == {"raw_json": "1", "limit": "500"}
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer token-value"
    assert "User-Agent" in headers


def test_fetch_reddit_thread_json_handles_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.headers = {}
    mock_response.raise_for_status = MagicMock()
    monkeypatch.setenv("REDDIT_BEARER_TOKEN", "token-value")
    monkeypatch.setattr("requests.get", lambda *a, **kw: mock_response)

    with pytest.raises(FetchError, match="token rejected or expired"):
        fetch_reddit_thread_json(
            "https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/my_title/",
            options=_options(),
            auth=_auth(),
        )


def test_fetch_reddit_thread_json_handles_429_with_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {"X-Ratelimit-Reset": "24"}
    mock_response.raise_for_status = MagicMock()
    monkeypatch.setenv("REDDIT_BEARER_TOKEN", "token-value")
    monkeypatch.setattr("requests.get", lambda *a, **kw: mock_response)

    with pytest.raises(FetchError, match="reset=24"):
        fetch_reddit_thread_json(
            "https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/my_title/",
            options=_options(),
            auth=_auth(),
        )


def test_reddit_thread_json_to_markdown_renders_post_and_comments() -> None:
    payload = [
        {
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "title": "Example title",
                            "subreddit": "ObsidianMD",
                            "author": "alice",
                            "score": 123,
                            "num_comments": 2,
                            "selftext": "Post body",
                        },
                    }
                ]
            }
        },
        {
            "data": {
                "children": [
                    {
                        "kind": "t1",
                        "data": {
                            "author": "bob",
                            "score": 10,
                            "body": "First comment",
                            "replies": {
                                "data": {
                                    "children": [
                                        {
                                            "kind": "t1",
                                            "data": {
                                                "author": "carol",
                                                "score": 3,
                                                "body": "Nested reply",
                                            },
                                        }
                                    ]
                                }
                            },
                        },
                    },
                    {"kind": "more", "data": {}},
                ]
            }
        },
    ]
    markdown = reddit_thread_json_to_markdown(
        payload,
        source_url="https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/my_title/",
    )
    assert markdown.startswith("# Example title")
    assert "- Subreddit: r/ObsidianMD" in markdown
    assert "Post body" in markdown
    assert "### u/bob · score 10" in markdown
    assert "#### u/carol · score 3" in markdown
