"""Terminal Markdown preview helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PreviewResult:
    rendered: bool
    text: str
    warning: str | None = None


def terminal_preview(
    markdown: str,
    *,
    max_lines: int | None = None,
    plain: bool = False,
) -> PreviewResult:
    if max_lines is not None:
        limited = markdown.splitlines()[:max_lines]
        markdown = "\n".join(limited)
        if markdown and not markdown.endswith("\n"):
            markdown += "\n"

    if plain:
        return PreviewResult(rendered=False, text=markdown)

    try:
        from rich.console import Console
        from rich.markdown import Markdown
    except ImportError:
        return PreviewResult(
            rendered=False,
            text=markdown,
            warning=(
                "Rich is not installed; using plain preview. "
                "Install htmlquill[rich] for terminal Markdown rendering."
            ),
        )

    console = Console(record=True)
    console.print(Markdown(markdown))
    return PreviewResult(rendered=True, text=console.export_text())
