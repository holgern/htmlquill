"""DOM-to-Markdown renderer for htmlquill."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import NavigableString, PageElement, Tag

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

_SIMPLE_TEX_REPLACEMENTS = {
    r"\rightarrow": "→",
    r"\to": "→",
    r"\times": "×",
    r"\sim": "∼",
    r"\ast": "∗",
}


def collapse_ws(value: str) -> str:
    """Collapse runs of whitespace to a single space."""
    return re.sub(r"\s+", " ", value)


def escape_text(value: str) -> str:
    """Escape Markdown-special characters in paragraph text.

    Does not escape inside code/pre blocks (callers must skip those).
    """
    return _TEXT_ESCAPE_RE.sub(r"\\\1", value)


def escape_link_label(value: str) -> str:
    """Escape characters in Markdown link labels [label]."""
    return value.replace("\\", "\\\\").replace("]", "\\]")


def escape_image_alt(value: str) -> str:
    """Escape characters in Markdown image alt text ![alt]."""
    return value.replace("\\", "\\\\").replace("]", "\\]")


def escape_url(value: str) -> str:
    """Escape a URL for use in Markdown links/images.

    Encodes spaces and parentheses that would break Markdown syntax.
    """
    # Encode spaces and unmatched parens that break Markdown link syntax
    return value.replace(" ", "%20").replace("(", "%28").replace(")", "%29")


def escape_table_cell(value: str) -> str:
    """Escape pipe characters and newlines in table cells."""
    return value.replace("|", "\\|").replace("\n", " ")


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
        self._in_code = False

    def render(self, node: Tag | NavigableString) -> str:
        """Render a DOM node tree to a Markdown string."""
        return self.render_node(node).strip()

    def render_children(self, node: Tag) -> str:
        """Render all children of a tag and concatenate."""
        return "".join(
            self.render_node(child)
            for child in node.children
            if isinstance(child, (Tag, NavigableString))
        )

    def render_node(self, node: Tag | NavigableString | PageElement) -> str:
        """Dispatch rendering based on node type."""
        if isinstance(node, NavigableString):
            text = collapse_ws(str(node))
            if self._in_code:
                return text
            return escape_text(text)
        if not isinstance(node, Tag):
            return ""

        name = node.name.lower()
        handler = getattr(self, f"render_{name.replace('-', '_')}", None)
        if handler is not None:
            return handler(node)  # type: ignore[no-any-return]

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
        self._in_code = True
        try:
            content = self.render_children(node).strip()
        finally:
            self._in_code = False
        return f"`{content}`"

    def render_math(self, node: Tag) -> str:
        tex = self._math_tex(node)
        if tex:
            return self._format_math(tex, display=self._is_display_math(node))

        rendered = collapse_ws(self.render_children(node).strip())
        if rendered:
            return rendered
        return collapse_ws(node.get_text(" ", strip=True))

    def render_semantics(self, node: Tag) -> str:
        # In MathML semantics trees, emit only the first visible child.
        for child in node.children:
            if isinstance(child, Tag):
                if child.name in {"annotation", "annotation-xml"}:
                    continue
                return self.render_node(child)
            if isinstance(child, NavigableString):
                text = collapse_ws(str(child)).strip()
                if text:
                    return text
        return ""

    def render_annotation(self, node: Tag) -> str:
        return ""

    def render_annotation_xml(self, node: Tag) -> str:
        return ""

    def _math_tex(self, node: Tag) -> str:
        # Prefer direct TeX metadata.
        for attr in ("alttext", "alt", "data-tex", "tex"):
            raw = str(node.get(attr) or "").strip()
            if raw:
                return self._clean_tex(raw)

        for ann in node.find_all(["annotation", "annotation-xml"]):
            encoding = str(ann.get("encoding") or "").lower()
            if "tex" not in encoding and "latex" not in encoding:
                continue
            raw = ann.get_text("", strip=True)
            if raw:
                return self._clean_tex(raw)

        return ""

    def _clean_tex(self, tex: str) -> str:
        tex = re.sub(r"\s+", " ", tex).strip()
        tex = tex.replace("\\displaystyle", "").strip()

        if tex.startswith(r"\(") and tex.endswith(r"\)"):
            tex = tex[2:-2].strip()
        if tex.startswith(r"\[") and tex.endswith(r"\]"):
            tex = tex[2:-2].strip()
        if tex.startswith("$$") and tex.endswith("$$"):
            tex = tex[2:-2].strip()

        tex = re.sub(r"italic_([A-Za-z])", r"\1", tex)

        for cmd, replacement in _SIMPLE_TEX_REPLACEMENTS.items():
            tex = tex.replace(cmd, replacement)

        return tex.strip()

    def _is_display_math(self, node: Tag) -> bool:
        display = str(node.get("display") or "").strip().lower()
        if display == "block":
            return True

        if self._has_display_math_class(node):
            return True

        for parent in node.parents:
            if isinstance(parent, Tag) and self._has_display_math_class(parent):
                return True
        return False

    def _has_display_math_class(self, node: Tag) -> bool:
        classes = node.get("class", [])
        if isinstance(classes, str):
            class_list = classes.split()
        else:
            class_list = [str(item) for item in classes]
        return any(
            cls in {"ltx_Math_Display", "ltx_equation", "ltx_equationgroup"}
            for cls in class_list
        )

    def _format_math(self, tex: str, *, display: bool) -> str:
        if tex in {"→", "×", "∼", "∗"}:
            return tex

        if len(tex) == 1 and tex.isalpha():
            return f"${tex}$"

        if display:
            return f"\n\n$$\n{tex}\n$$\n\n"

        return f"${tex}$"

    # --- Links and images ---

    def render_a(self, node: Tag) -> str:
        text = self.render_children(node).strip() or node.get_text(strip=True)
        href = str(node.get("href") or "").strip()
        if not text:
            return ""
        if not href or href.lower().startswith("javascript:"):
            return text
        if href.lower().startswith("mailto:"):
            return text
        absolute_href = urljoin(self.base_url or "", href)
        safe_href = escape_url(absolute_href)
        # Note: do not escape ] in label here because it may contain
        # rendered image/link syntax from children.
        return f"[{text}]({safe_href})"

    def render_img(self, node: Tag) -> str:
        alt = str(node.get("alt") or "").strip()

        # Check for picture > source srcset from parent
        src = self._resolve_image_src(node)

        if not src:
            return ""
        absolute_src = urljoin(self.base_url or "", src)
        safe_src = escape_url(absolute_src)
        safe_alt = escape_image_alt(alt)
        return f"![{safe_alt}]({safe_src})"

    def render_picture(self, node: Tag) -> str:
        # Render the img child inside a picture element
        img = node.find("img")
        if isinstance(img, Tag):
            return self.render_img(img)
        return ""

    def render_figure(self, node: Tag) -> str:
        caption = node.find("figcaption")
        rendered_parts: list[str] = []

        for child in node.children:
            if isinstance(child, Tag) and child.name == "figcaption":
                continue
            part = self.render_node(child).strip()
            if part:
                rendered_parts.append(part)

        if caption is not None:
            caption_text = self.render_children(caption).strip()
            if caption_text:
                rendered_parts.append(f"**{caption_text}**")

        if not rendered_parts:
            return ""
        return "\n\n" + "\n\n".join(rendered_parts) + "\n\n"

    def render_figcaption(self, node: Tag) -> str:
        text = self.render_children(node).strip()
        if not text:
            return ""
        return f"\n\n**{text}**\n\n"

    def render_svg(self, node: Tag) -> str:
        title = node.find("title")
        desc = node.find("desc")

        labels: list[str] = []
        for part in (title, desc):
            if part is None:
                continue
            text = part.get_text(" ", strip=True)
            if text:
                labels.append(text)

        label = " ".join(labels).strip()
        if label:
            return f"[SVG figure: {label}]"
        return "[SVG figure omitted]"

    def _resolve_image_src(self, img: Tag) -> str:
        """Resolve the best image source URL from various attributes."""

        # 1. Check srcset on the img itself (pick highest resolution)
        srcset = str(img.get("srcset") or "").strip()
        if srcset:
            best = self._pick_best_srcset(srcset)
            if best:
                return best

        # 2. Check for picture > source srcset
        parent = img.parent
        if parent is not None and isinstance(parent, Tag) and parent.name == "picture":
            for source in parent.find_all("source"):
                srcset = str(source.get("srcset") or "").strip()
                if srcset:
                    best = self._pick_best_srcset(srcset)
                    if best:
                        return best

        # 3. Check data-src, data-original
        for attr in ("data-src", "data-original"):
            val = str(img.get(attr) or "").strip()
            if val:
                return val

        # 4. Fall back to src
        return str(img.get("src") or "").strip()

    def _pick_best_srcset(self, srcset: str) -> str:
        """Parse srcset and return the URL with the highest width descriptor."""
        best_url = ""
        best_width = -1
        for entry in srcset.split(","):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split()
            url = parts[0]
            width = 0
            if len(parts) > 1:
                # Parse width descriptor like "1280w"
                m = re.match(r"(\d+)w", parts[1])
                if m:
                    width = int(m.group(1))
            if width > best_width:
                best_width = width
                best_url = url
        return best_url

    # --- Lists ---

    def render_ul(self, node: Tag) -> str:
        items = []
        for child in node.children:
            if isinstance(child, Tag) and child.name == "li":
                items.append(
                    self._render_list_item(
                        child,
                        bullet="-",
                        indent=0,
                        ordered=False,
                    )
                )
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
                    self._render_list_item(
                        child,
                        bullet=f"{counter}.",
                        indent=0,
                        ordered=True,
                    )
                )
                counter += 1
            elif isinstance(child, Tag) and child.name in ("ul", "ol"):
                items.append(self._render_nested_list(child, indent=0))
        content = "\n".join(items)
        return f"\n\n{content}\n\n"

    def render_li(self, node: Tag) -> str:
        # Standalone li (shouldn't normally happen, but be safe)
        return self._render_list_item(node, bullet="-", indent=0, ordered=False)

    def _render_list_item(
        self,
        node: Tag,
        bullet: str,
        indent: int,
        *,
        ordered: bool = False,
    ) -> str:
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

        content = " ".join(inline_content)
        content = self._strip_list_marker_prefix(content, ordered=ordered)

        line = prefix + content if content else prefix.rstrip()
        if sub_lists:
            return line + "\n" + "\n".join(sub_lists)
        return line

    def _render_nested_list(self, node: Tag, indent: int) -> str:
        items: list[str] = []
        if node.name == "ul":
            for child in node.children:
                if isinstance(child, Tag) and child.name == "li":
                    items.append(
                        self._render_list_item(
                            child,
                            bullet="-",
                            indent=indent,
                            ordered=False,
                        )
                    )
                elif isinstance(child, Tag) and child.name in ("ul", "ol"):
                    items.append(self._render_nested_list(child, indent=indent))
        elif node.name == "ol":
            counter = 1
            for child in node.children:
                if isinstance(child, Tag) and child.name == "li":
                    items.append(
                        self._render_list_item(
                            child,
                            bullet=f"{counter}.",
                            indent=indent,
                            ordered=True,
                        )
                    )
                    counter += 1
                elif isinstance(child, Tag) and child.name in ("ul", "ol"):
                    items.append(self._render_nested_list(child, indent=indent))
        return "\n".join(items)

    def _strip_list_marker_prefix(self, text: str, *, ordered: bool) -> str:
        cleaned = text.strip()
        if ordered:
            cleaned = re.sub(r"^\s*\d+[.)]\s+", "", cleaned)
        cleaned = re.sub(r"^\s*[•‣◦▪▫]\s*", "", cleaned)
        return cleaned.strip()

    # --- Code blocks ---

    def render_pre(self, node: Tag) -> str:
        # Check if there's a <code> child
        code_tag = node.find("code")
        if isinstance(code_tag, Tag):
            lang = ""
            # Try to detect language from class like "language-python"
            classes: list[str] | str = code_tag.get("class", []) or []
            if isinstance(classes, list):
                for cls in classes:
                    if cls.startswith("language-"):
                        lang = cls[len("language-") :]
                        break
            self._in_code = True
            try:
                code_text = self._pre_text(code_tag)
            finally:
                self._in_code = False
        else:
            lang = ""
            self._in_code = True
            try:
                code_text = self._pre_text(node)
            finally:
                self._in_code = False
        return f"\n\n```{lang}\n{code_text}\n```\n\n"

    def _pre_text(self, node: Tag) -> str:
        """Extract text from a pre/code node, reconstructing line boundaries."""
        # Check for Medium-style line wrappers: pre div, pre p, pre span[data-testid]
        line_containers = node.select("div, p")
        if line_containers:
            lines: list[str] = []
            for container in line_containers:
                line_text = container.get_text("", strip=False).rstrip("\n")
                lines.append(line_text)
            return "\n".join(lines)

        # Check for span-based line wrappers (e.g., [data-line], .line)
        span_lines = node.select("[data-line], .line")
        if span_lines:
            return "\n".join(
                span.get_text("", strip=False).rstrip("\n") for span in span_lines
            )

        # Default: use get_text with newline separator to handle nested spans
        return str(node.get_text(""))

    # --- Tables ---

    def render_table(self, node: Tag) -> str:
        if self._is_complex_table(node):
            return self._render_complex_table_as_html(node)

        rows: list[list[str]] = []
        for row_tag in self._iter_table_rows(node):
            cells = row_tag.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            rows.append([self._table_cell_text(cell) for cell in cells])

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

    def _iter_table_rows(self, node: Tag) -> list[Tag]:
        rows: list[Tag] = []
        for section_name in ("thead", "tbody", "tfoot"):
            for section in node.find_all(section_name, recursive=False):
                rows.extend(section.find_all("tr", recursive=False))
        rows.extend(node.find_all("tr", recursive=False))
        return rows

    def _table_cell_text(self, cell: Tag) -> str:
        text = self.render_children(cell).strip()
        text = re.sub(r"\n\s*\n+", "<br><br>", text)
        text = re.sub(r"\n+", "<br>", text)
        text = text.replace("|", r"\|")
        return text.strip()

    def _is_complex_table(self, node: Tag) -> bool:
        # Nested table descendants cannot be represented safely as markdown pipes.
        if node.find("table") is not None:
            return True

        for cell in node.find_all(["th", "td"]):
            if cell.find("table") is not None:
                return True
            if cell.has_attr("rowspan") or cell.has_attr("colspan"):
                return True
            if len(cell.get_text(" ", strip=True)) > 800:
                return True

        return False

    def _render_complex_table_as_html(self, node: Tag) -> str:
        return "\n\n" + str(node) + "\n\n"
