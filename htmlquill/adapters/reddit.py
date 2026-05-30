"""Reddit API adapter."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

from htmlquill.auth import ResolvedAuth
from htmlquill.config import ResolvedOptions
from htmlquill.fetch import DEFAULT_USER_AGENT, FetchError

_REDDIT_COMMENTS_RE = re.compile(
    r"^/r/(?P<subreddit>[^/]+)/comments/(?P<post_id>[A-Za-z0-9]+)"
    r"(?:/(?P<slug>[^/]*))?(?:/.*)?$"
)


@dataclass(frozen=True)
class RedditPostRef:
    subreddit: str
    post_id: str
    slug: str | None = None


def parse_reddit_url(url: str) -> RedditPostRef | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in {
        "reddit.com",
        "www.reddit.com",
        "old.reddit.com",
        "m.reddit.com",
        "np.reddit.com",
    }:
        return None

    match = _REDDIT_COMMENTS_RE.match(parsed.path)
    if not match:
        return None

    slug = match.group("slug") or None
    return RedditPostRef(
        subreddit=match.group("subreddit"),
        post_id=match.group("post_id"),
        slug=slug,
    )


def reddit_api_url(ref: RedditPostRef) -> str:
    return f"https://oauth.reddit.com/comments/{ref.post_id}"


def fetch_reddit_thread_json(
    url: str,
    *,
    options: ResolvedOptions,
    auth: ResolvedAuth,
) -> Any:
    ref = parse_reddit_url(url)
    if ref is None:
        raise FetchError(f"not a supported Reddit comments URL: {url!r}")

    token: str
    if auth.bearer_token:
        token = auth.bearer_token.strip()
    elif auth.token_env:
        token = os.environ.get(auth.token_env, "").strip()
    else:
        raise FetchError(
            "Reddit API adapter requires a bearer token. "
            "Run `htmlquill auth login reddit` or configure an auth profile "
            "with token_env."
        )
        raise FetchError(
            "Reddit API adapter requires a bearer token. "
            "Run `htmlquill auth login reddit` or configure an auth profile "
            "with token_env."
        )

    if not token:
        raise FetchError(
            "Reddit API bearer token is empty"
        )

    user_agent = options.headers.get("User-Agent", "").strip()
    if not user_agent or user_agent == DEFAULT_USER_AGENT:
        raise FetchError(
            "Reddit API adapter requires a descriptive User-Agent; set "
            "[sites.\"reddit.com\"].user_agent."
        )

    try:
        response = requests.get(
            reddit_api_url(ref),
            params={"raw_json": "1", "limit": "500"},
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": user_agent,
                "Accept": "application/json",
            },
            timeout=options.timeout,
        )
    except requests.RequestException as exc:
        raise FetchError(f"Reddit API request failed for {url!r}: {exc}") from exc

    if response.status_code in {401, 403}:
        raise FetchError("Reddit API token rejected or expired")
    if response.status_code == 404:
        raise FetchError("Reddit thread not found via Reddit API")
    if response.status_code == 429:
        reset = response.headers.get("X-Ratelimit-Reset")
        raise FetchError(f"Reddit API rate limited; reset={reset or 'unknown'} seconds")

    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"Reddit API request failed for {url!r}: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise FetchError("Reddit API returned invalid JSON payload") from exc

    if not isinstance(payload, list) or len(payload) < 2:
        raise FetchError("Reddit API returned an unsupported thread payload shape")
    return payload


def _listing_children(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    children = data.get("children")
    if not isinstance(children, list):
        return []
    return [item for item in children if isinstance(item, dict)]


def _comment_markdown_lines(children: list[dict[str, Any]], *, depth: int) -> list[str]:
    lines: list[str] = []
    heading_level = min(6, 3 + depth)
    heading = "#" * heading_level

    for child in children:
        kind = child.get("kind")
        data = child.get("data")
        if kind == "more":
            continue
        if kind != "t1" or not isinstance(data, dict):
            continue

        author = data.get("author")
        author_text = str(author) if isinstance(author, str) and author else "[deleted]"
        score = data.get("score")
        score_text = str(score) if isinstance(score, int) else "0"
        body = data.get("body")
        body_text = str(body).strip() if isinstance(body, str) else ""
        if not body_text:
            body_text = "[deleted]"

        lines.append(f"{heading} u/{author_text} · score {score_text}")
        lines.append("")
        lines.append(body_text)
        lines.append("")

        replies = data.get("replies")
        if isinstance(replies, dict):
            reply_children = _listing_children(replies)
            if reply_children:
                lines.extend(_comment_markdown_lines(reply_children, depth=depth + 1))
    return lines


def reddit_thread_json_to_markdown(payload: Any, *, source_url: str) -> str:
    if not isinstance(payload, list) or len(payload) < 2:
        raise FetchError("Reddit API returned an unsupported thread payload shape")

    post_listing = payload[0]
    comments_listing = payload[1]
    post_children = _listing_children(post_listing)
    if not post_children:
        raise FetchError("Reddit API payload does not include post data")

    post_data = post_children[0].get("data")
    if not isinstance(post_data, dict):
        raise FetchError("Reddit API payload includes invalid post data")

    title = post_data.get("title")
    subreddit = post_data.get("subreddit")
    author = post_data.get("author")
    score = post_data.get("score")
    num_comments = post_data.get("num_comments")
    selftext = post_data.get("selftext")
    post_url = post_data.get("url")

    title_text = (
        str(title).strip() if isinstance(title, str) and title else "Reddit Post"
    )
    subreddit_text = (
        str(subreddit) if isinstance(subreddit, str) and subreddit else "unknown"
    )
    author_text = str(author) if isinstance(author, str) and author else "[deleted]"
    score_text = str(score) if isinstance(score, int) else "0"
    comments_text = str(num_comments) if isinstance(num_comments, int) else "0"

    lines = [
        f"# {title_text}",
        "",
        f"- Subreddit: r/{subreddit_text}",
        f"- Author: u/{author_text}",
        f"- Score: {score_text}",
        f"- Comments: {comments_text}",
        f"- Source: {source_url}",
        "",
    ]

    if isinstance(selftext, str) and selftext.strip():
        lines.append(selftext.strip())
        lines.append("")
    elif isinstance(post_url, str) and post_url.strip():
        lines.append(post_url.strip())
        lines.append("")

    lines.append("## Comments")
    lines.append("")

    comment_children = _listing_children(comments_listing)
    if not comment_children:
        lines.append("_No comments returned by Reddit API._")
        lines.append("")
    else:
        lines.extend(_comment_markdown_lines(comment_children, depth=0))

    return "\n".join(lines).strip() + "\n"
