"""DOM-to-Markdown renderer for htmlquill."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import NavigableString, Tag

BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "div",
    "dl",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "ul",
}


def collapse_ws(value: str) -> str:
    """Collapse runs of whitespace to a single space."""
    return re.sub(r"\s+", " ", value)


def normalize_markdown(markdown: str) -> str:
    """Normalize Markdown output: strip trailing whitespace,
    collapse blank lines, ensure trailing newline."""
    lines = [line.rstrip() for line in markdown.splitlines()]
    text = "\n".join(lines)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip() + "\n"


class MarkdownRenderer:
    """Recursive DOM visitor that converts HTML elements to Markdown."""

    def __init__(self, *, base_url: str | None = None) -> None:
        self.base_url = base_url

    def render(self, node: Tag | NavigableString) -> str:
        """Render a DOM node tree to a Markdown string."""
        return self.render_node(node).strip()

    def render_children(self, node: Tag) -> str:
        """Render all children of a tag and concatenate."""
        return "".join(self.render_node(child) for child in node.children)

    def render_node(self, node: Tag | NavigableString) -> str:
        """Dispatch rendering based on node type."""
        if isinstance(node, NavigableString):
            return collapse_ws(str(node))
        if not isinstance(node, Tag):
            return ""

        name = node.name.lower()
        handler = getattr(self, f"render_{name}", None)
        if handler is not None:
            return handler(node)

        content = self.render_children(node)
        if name in BLOCK_TAGS:
            return f"\n\n{content.strip()}\n\n"
        return content

    # --- Headings ---

    def render_h1(self, node: Tag) -> str:
        return self._heading(node, 1)

    def render_h2(self, node: Tag) -> str:
        return self._heading(node, 2)

    def render_h3(self, node: Tag) -> str:
        return self._heading(node, 3)

    def render_h4(self, node: Tag) -> str:
        return self._heading(node, 4)

    def render_h5(self, node: Tag) -> str:
        return self._heading(node, 5)

    def render_h6(self, node: Tag) -> str:
        return self._heading(node, 6)

    def _heading(self, node: Tag, level: int) -> str:
        text = self.render_children(node).strip()
        return f"\n\n{'#' * level} {text}\n\n"

    # --- Block elements ---

    def render_p(self, node: Tag) -> str:
        return f"\n\n{self.render_children(node).strip()}\n\n"

    def render_blockquote(self, node: Tag) -> str:
        content = self.render_children(node).strip()
        lines = content.split("\n")
        quoted = "\n".join(f"> {line}" for line in lines)
        return f"\n\n{quoted}\n\n"

    def render_hr(self, node: Tag) -> str:
        return "\n\n---\n\n"

    def render_br(self, node: Tag) -> str:
        return "\n"

    # --- Inline elements ---

    def render_strong(self, node: Tag) -> str:
        return f"**{self.render_children(node).strip()}**"

    def render_b(self, node: Tag) -> str:
        return self.render_strong(node)

    def render_em(self, node: Tag) -> str:
        return f"*{self.render_children(node).strip()}*"

    def render_i(self, node: Tag) -> str:
        return self.render_em(node)

    def render_code(self, node: Tag) -> str:
        # If inside <pre>, just return the text
        if node.parent and node.parent.name == "pre":
            return self.render_children(node)
        return f"`{self.render_children(node).strip()}`"

    # --- Links and images ---

    def render_a(self, node: Tag) -> str:
        text = self.render_children(node).strip() or node.get_text(strip=True)
        href = str(node.get("href") or "").strip()
        if not href or href.lower().startswith("javascript:"):
            return text
        if href.lower().startswith("mailto:"):
            return text
        absolute_href = urljoin(self.base_url or "", href)
        return f"[{text}]({absolute_href})"

    def render_img(self, node: Tag) -> str:
        alt = str(node.get("alt") or "").strip()
        src = str(node.get("src") or "").strip()
        if not src:
            return ""
        absolute_src = urljoin(self.base_url or "", src)
        return f"![{alt}]({absolute_src})"

    # --- Lists ---

    def render_ul(self, node: Tag) -> str:
        items = []
        for child in node.children:
            if isinstance(child, Tag) and child.name == "li":
                items.append(self._render_list_item(child, bullet="-", indent=0))
            elif isinstance(child, Tag) and child.name in ("ul", "ol"):
                items.append(self._render_nested_list(child, indent=0))
        content = "\n".join(items)
        return f"\n\n{content}\n\n"

    def render_ol(self, node: Tag) -> str:
        items = []
        counter = 1
        for child in node.children:
            if isinstance(child, Tag) and child.name == "li":
                items.append(
                    self._render_list_item(child, bullet=f"{counter}.", indent=0)
                )
                counter += 1
            elif isinstance(child, Tag) and child.name in ("ul", "ol"):
                items.append(self._render_nested_list(child, indent=0))
        content = "\n".join(items)
        return f"\n\n{content}\n\n"

    def render_li(self, node: Tag) -> str:
        # Standalone li (shouldn't normally happen, but be safe)
        return self._render_list_item(node, bullet="-", indent=0)

    def _render_list_item(self, node: Tag, bullet: str, indent: int) -> str:
        prefix = "  " * indent + f"{bullet} "
        inline_content: list[str] = []
        sub_lists: list[str] = []

        for child in node.children:
            if isinstance(child, Tag) and child.name in ("ul", "ol"):
                sub_lists.append(self._render_nested_list(child, indent=indent + 1))
            elif isinstance(child, Tag) and child.name == "p":
                inline_content.append(self.render_children(child).strip())
            else:
                text = self.render_node(child).strip()
                if text:
                    inline_content.append(text)

        line = prefix + " ".join(inline_content)
        if sub_lists:
            return line + "\n" + "\n".join(sub_lists)
        return line

    def _render_nested_list(self, node: Tag, indent: int) -> str:
        items: list[str] = []
        if node.name == "ul":
            for child in node.children:
                if isinstance(child, Tag) and child.name == "li":
                    items.append(
                        self._render_list_item(child, bullet="-", indent=indent)
                    )
                elif isinstance(child, Tag) and child.name in ("ul", "ol"):
                    items.append(self._render_nested_list(child, indent=indent))
        elif node.name == "ol":
            counter = 1
            for child in node.children:
                if isinstance(child, Tag) and child.name == "li":
                    items.append(
                        self._render_list_item(
                            child, bullet=f"{counter}.", indent=indent
                        )
                    )
                    counter += 1
                elif isinstance(child, Tag) and child.name in ("ul", "ol"):
                    items.append(self._render_nested_list(child, indent=indent))
        return "\n".join(items)

    # --- Code blocks ---

    def render_pre(self, node: Tag) -> str:
        # Check if there's a <code> child
        code_tag = node.find("code")
        if code_tag is not None:
            lang = ""
            # Try to detect language from class like "language-python"
            classes = code_tag.get("class", [])
            if isinstance(classes, list):
                for cls in classes:
                    if cls.startswith("language-"):
                        lang = cls[len("language-") :]
                        break
            code_text = code_tag.get_text()
        else:
            lang = ""
            code_text = node.get_text()
        return f"\n\n```{lang}\n{code_text}\n```\n\n"

    # --- Tables ---

    def render_table(self, node: Tag) -> str:
        rows: list[list[str]] = []
        for tag in node.find_all("tr"):
            cells = tag.find_all(["th", "td"])
            row = [self.render_children(cell).strip() for cell in cells]
            rows.append(row)

        if not rows:
            return ""

        # Determine column count
        col_count = max(len(row) for row in rows)

        # Pad rows
        for row in rows:
            while len(row) < col_count:
                row.append("")

        # Build markdown table
        lines: list[str] = []
        for i, row in enumerate(rows):
            line = "| " + " | ".join(row) + " |"
            lines.append(line)
            if i == 0:
                sep = "| " + " | ".join("---" for _ in range(col_count)) + " |"
                lines.append(sep)

        return f"\n\n{chr(10).join(lines)}\n\n"
