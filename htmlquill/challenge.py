"""Challenge/interstitial page detection helpers."""

from __future__ import annotations

from collections.abc import Sequence

DEFAULT_CHALLENGE_MARKERS: tuple[str, ...] = (
    "Performing security verification",
    "security service to protect against malicious bots",
    "verifies you are not a bot",
    "Checking if the site connection is secure",
    "Just a moment",
)


class ChallengePageError(RuntimeError):
    """Raised when fetched HTML appears to be a challenge page."""


def is_challenge_page(
    html: str,
    url: str | None = None,
    markers: Sequence[str] = DEFAULT_CHALLENGE_MARKERS,
) -> bool:
    """Return ``True`` if *html* contains known challenge page markers."""

    del url  # reserved for future URL-specific marker behavior
    lower = html.lower()
    return any(marker.lower() in lower for marker in markers)


def assert_not_challenge_page(
    html: str,
    *,
    url: str | None = None,
    markers: Sequence[str] = DEFAULT_CHALLENGE_MARKERS,
) -> None:
    """Raise :class:`ChallengePageError` when *html* looks like an interstitial."""

    if is_challenge_page(html, url=url, markers=markers):
        raise ChallengePageError(
            "received a security verification page instead of article HTML"
        )
