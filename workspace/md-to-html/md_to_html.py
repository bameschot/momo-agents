"""
md_to_html.py — Markdown to HTML Bundler

A single-file, self-contained Python CLI script that accepts a glob pattern
matching one or more Markdown files and bundles them into a single styled HTML file.

Requirements: Python 3.11+, stdlib only.
"""

from __future__ import annotations

import argparse
import base64
import glob as glob_module
import mimetypes
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class Heading:
    level: int      # 1–6
    text: str       # Plain text of the heading
    anchor: str     # Slugified anchor ID


@dataclass
class FileEntry:
    path: Path               # Absolute path to the .md file
    slug: str                # Filename stem, slugified (used as anchor)
    title: str               # First # heading text, or slug if none found
    raw_markdown: str        # Raw file contents
    html_body: str           # Parsed HTML fragment
    headings: list[Heading] = field(default_factory=list)  # All headings extracted, in order


@dataclass
class RenderContext:
    output_path: Path
    title: str               # Derived from output filename stem
    entries: list[FileEntry] = field(default_factory=list)
    toc: str = ""            # Pre-rendered TOC HTML


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug for heading IDs."""
    text = text.lower()
    text = text.replace(" ", "-")
    text = re.sub(r"[^a-z0-9\-]", "", text)
    text = re.sub(r"-{2,}", "-", text)
    text = text.strip("-")
    return text


def html_escape(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# Image Embedder
# ---------------------------------------------------------------------------

def embed_image(path: str, source_md_path: Path) -> str:
    """
    Resolve *path* relative to *source_md_path.parent* and return a data URI.

    Returns the original *path* string unchanged if:
    - path starts with http:// or https://
    - the resolved local file does not exist or cannot be read
    """
    if path.startswith("http://") or path.startswith("https://"):
        return path

    resolved = (source_md_path.parent / path).resolve()
    try:
        data = resolved.read_bytes()
    except (OSError, IOError):
        return path

    mime, _ = mimetypes.guess_type(str(resolved))
    if mime is None:
        mime = "application/octet-stream"

    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


# ---------------------------------------------------------------------------
# Inline Processor
# ---------------------------------------------------------------------------

def _process_inline(text: str, source_path: Path | None = None) -> str:
    """
    Process inline Markdown elements in *text* and return HTML.

    Processing order (using placeholder tokens):
    1. Extract code spans (to avoid processing their contents)
    2. Extract inline HTML (to avoid double-escaping)
    3. HTML-escape remaining text
    4. Process images (before links, to avoid '![' being consumed as '[')
    5. Process links
    6. Bold-italic, bold, italic, strikethrough
    7. Hard line breaks
    8. Restore placeholders
    """
    placeholders: dict[str, str] = {}

    def store(html: str) -> str:
        key = f"\x00PH{uuid.uuid4().hex}\x00"
        placeholders[key] = html
        return key

    # 1. Extract code spans
    def replace_code(m: re.Match) -> str:
        content = html_escape(m.group(1))
        return store(f"<code>{content}</code>")

    text = re.sub(r"`(.+?)`", replace_code, text)

    # 2. Extract inline HTML tags (e.g. <br>, <span class="x">)
    def replace_inline_html(m: re.Match) -> str:
        return store(m.group(0))

    text = re.sub(r"<[a-zA-Z/][^>]*>", replace_inline_html, text)

    # 3. HTML-escape remaining text
    text = html_escape(text)

    # 4. Process images
    def replace_image(m: re.Match) -> str:
        alt = m.group(1)
        path = m.group(2)
        if source_path is not None:
            src = embed_image(path, source_path)
        else:
            src = path
        return store(f'<img src="{src}" alt="{alt}">')

    text = re.sub(r"!\[([^\]]*)\]\(([^)]*)\)", replace_image, text)

    # 5. Process links
    def replace_link(m: re.Match) -> str:
        link_text = m.group(1)
        url = m.group(2)
        return store(f'<a href="{url}">{link_text}</a>')

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_link, text)

    # 6. Bold-italic, bold, italic, strikethrough
    # Bold-italic: ***text*** or ___text___
    text = re.sub(r"\*{3}(.+?)\*{3}", lambda m: store(f"<strong><em>{m.group(1)}</em></strong>"), text)
    text = re.sub(r"_{3}(.+?)_{3}", lambda m: store(f"<strong><em>{m.group(1)}</em></strong>"), text)

    # Bold: **text** or __text__
    text = re.sub(r"\*{2}(.+?)\*{2}", lambda m: store(f"<strong>{m.group(1)}</strong>"), text)
    text = re.sub(r"(?<!\w)__(?!\s)(.+?)(?<!\s)__(?!\w)", lambda m: store(f"<strong>{m.group(1)}</strong>"), text)

    # Italic: *text* or _text_
    text = re.sub(r"\*(.+?)\*", lambda m: store(f"<em>{m.group(1)}</em>"), text)
    text = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", lambda m: store(f"<em>{m.group(1)}</em>"), text)

    # Strikethrough: ~~text~~
    text = re.sub(r"~~(.+?)~~", lambda m: store(f"<del>{m.group(1)}</del>"), text)

    # 7. Hard line breaks (backslash at end of line — two-space breaks handled in block layer)
    text = re.sub(r"\\\n", "<br>\n", text)
    text = re.sub(r"  \n", "<br>\n", text)

    # 8. Restore placeholders
    # Keep restoring until no placeholders remain (handles nesting)
    for _ in range(20):
        new_text = text
        for key, value in placeholders.items():
            new_text = new_text.replace(key, value)
        if new_text == text:
            break
        text = new_text

    return text


# ---------------------------------------------------------------------------
# Markdown Parser — Block Elements
# ---------------------------------------------------------------------------

class MarkdownParser:
    """
    Parse Markdown text into an HTML fragment string.

    Block elements are fully implemented. Inline elements (including footnotes)
    are processed via _process_inline().
    """

    def __init__(self, source_path: Path | None = None) -> None:
        self.headings: list[Heading] = []
        self._source_path = source_path
        # Footnote state — reset at each parse() call
        self._fn_defs: dict[str, str] = {}      # label → definition text
        self._fn_refs: list[str] = []           # ordered by first reference

    def parse(self, markdown: str, source_path: Path | None = None) -> str:
        """Parse *markdown* and return an HTML fragment string."""
        self.headings = []
        effective_source = source_path if source_path is not None else self._source_path
        self._effective_source = effective_source
        # Reset footnote state for this parse call
        self._fn_defs = {}
        self._fn_refs = []

        # Pre-process: extract footnote definitions from line stream
        lines = self._extract_footnote_defs(markdown.splitlines())
        blocks = self._split_blocks(lines)
        html_parts: list[str] = []
        for block in blocks:
            html_parts.append(self._render_block(block))
        main_html = "\n".join(p for p in html_parts if p)

        # Replace [^label] references in main HTML
        main_html = self._replace_footnote_refs(main_html)

        # Append footnotes section if any were referenced
        if self._fn_refs:
            main_html += "\n" + self._render_footnotes_section()

        return main_html

    def _extract_footnote_defs(self, lines: list[str]) -> list[str]:
        """
        Extract `[^label]: definition` lines (with optional indented continuation)
        from *lines*, storing them in self._fn_defs.  Returns the remaining lines.
        """
        result: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            m = re.match(r"^\[(\^[^\]]+)\]:\s*(.*)", line)
            if m:
                label = m.group(1)  # includes the ^ prefix
                def_text = m.group(2)
                i += 1
                # Collect continuation lines (indented 4 spaces or a tab)
                while i < len(lines):
                    cont = lines[i]
                    if cont.startswith("    ") or cont.startswith("\t"):
                        def_text += " " + cont.strip()
                        i += 1
                    else:
                        break
                self._fn_defs[label] = def_text.strip()
            else:
                result.append(line)
                i += 1
        return result

    def _replace_footnote_refs(self, html: str) -> str:
        """Replace [^label] inline references in *html* with superscript links."""
        def replace_ref(m: re.Match) -> str:
            label = m.group(1)  # includes ^ prefix
            if label not in self._fn_refs:
                self._fn_refs.append(label)
            n = self._fn_refs.index(label) + 1
            if label not in self._fn_defs:
                import sys as _sys
                print(f"Warning: footnote {label!r} referenced but not defined", file=_sys.stderr)
                return f'<sup><a href="#fn-{label[1:]}" id="fnref-{label[1:]}">[?]</a></sup>'
            return f'<sup><a href="#fn-{label[1:]}" id="fnref-{label[1:]}">[{n}]</a></sup>'

        return re.sub(r"\[(\^[^\]]+)\](?!\:)", replace_ref, html)

    def _render_footnotes_section(self) -> str:
        """Render the `<section class="footnotes">` block."""
        items: list[str] = []
        for label in self._fn_refs:
            label_slug = label[1:]  # strip '^'
            def_text = self._fn_defs.get(label, "")
            rendered_def = _process_inline(def_text, self._effective_source)
            backlink = f'<a href="#fnref-{label_slug}">&#x21A9;</a>'
            items.append(
                f'<li id="fn-{label_slug}">{rendered_def} {backlink}</li>'
            )
        ol = "<ol>\n" + "\n".join(items) + "\n</ol>"
        return f'<section class="footnotes">\n{ol}\n</section>'

    def _inline(self, text: str) -> str:
        """Process inline Markdown in *text* (footnote refs handled separately in parse())."""
        return _process_inline(text, self._effective_source)

    # ------------------------------------------------------------------
    # Block splitting
    # ------------------------------------------------------------------

    def _split_blocks(self, lines: list[str]) -> list[list[str]]:
        """
        Split *lines* into logical blocks separated by blank lines,
        respecting fenced code blocks.
        """
        blocks: list[list[str]] = []
        current: list[str] = []
        in_fence = False
        fence_char = ""

        for line in lines:
            stripped = line.strip()

            # Detect fence open/close
            if not in_fence:
                m = re.match(r"^(`{3,}|~{3,})", line)
                if m:
                    in_fence = True
                    fence_char = m.group(1)[0]
                    if current:
                        blocks.append(current)
                    current = [line]
                    continue
            else:
                # Inside fence — look for closing fence
                m = re.match(r"^(`{3,}|~{3,})", line)
                if m and m.group(1)[0] == fence_char and len(m.group(1)) >= 3:
                    current.append(line)
                    blocks.append(current)
                    current = []
                    in_fence = False
                    fence_char = ""
                else:
                    current.append(line)
                continue

            if stripped == "":
                if current:
                    blocks.append(current)
                    current = []
            else:
                current.append(line)

        if current:
            blocks.append(current)

        return blocks

    # ------------------------------------------------------------------
    # Block rendering dispatcher
    # ------------------------------------------------------------------

    def _render_block(self, block: list[str]) -> str:
        if not block:
            return ""

        first = block[0]
        stripped_first = first.strip()

        # Fenced code block
        m = re.match(r"^(`{3,}|~{3,})(.*)", first)
        if m:
            return self._render_fenced_code(block, m)

        # ATX heading
        m = re.match(r"^(#{1,6})\s+(.*)", first)
        if m and len(block) == 1:
            return self._render_heading(m)

        # Horizontal rule (must be checked before list/blockquote)
        if self._is_hr(stripped_first) and len(block) == 1:
            return "<hr>"

        # Blockquote
        if stripped_first.startswith(">"):
            return self._render_blockquote(block)

        # GFM table — first two lines must be table rows
        if len(block) >= 2 and self._is_table_row(block[0]) and self._is_separator_row(block[1]):
            return self._render_table(block)

        # Unordered list
        if re.match(r"^(\s*)[-*+]\s", first):
            return self._render_list(block, ordered=False)

        # Ordered list
        if re.match(r"^(\s*)\d+\.\s", first):
            return self._render_list(block, ordered=True)

        # Raw HTML passthrough
        if self._is_raw_html(stripped_first):
            return "\n".join(block)

        # Paragraph
        return self._render_paragraph(block)

    # ------------------------------------------------------------------
    # Individual block renderers
    # ------------------------------------------------------------------

    def _render_heading(self, m: re.Match) -> str:
        level = len(m.group(1))
        text = m.group(2).strip()
        anchor = slugify(text)  # Use plain text for anchor generation
        self.headings.append(Heading(level=level, text=text, anchor=anchor))
        inline_text = self._inline(text)
        return f'<h{level} id="{anchor}">{inline_text}</h{level}>'

    def _render_fenced_code(self, block: list[str], m: re.Match) -> str:
        lang = m.group(2).strip()
        # Content is everything between first and last line
        content_lines = block[1:-1] if len(block) > 1 else []
        content = html_escape("\n".join(content_lines))
        if lang:
            return f'<pre><code class="language-{lang}">{content}</code></pre>'
        else:
            return f"<pre><code>{content}</code></pre>"

    def _render_paragraph(self, block: list[str]) -> str:
        text = self._process_paragraph_lines(block)
        return f"<p>{text}</p>"

    def _process_paragraph_lines(self, lines: list[str]) -> str:
        """Join paragraph lines, handling hard line breaks, then apply inline processing."""
        parts: list[str] = []
        for i, line in enumerate(lines):
            if line.endswith("  ") or line.endswith("\\ "):
                parts.append(line.rstrip())
                if i < len(lines) - 1:
                    parts.append("  \n")
            elif line.endswith("\\"):
                parts.append(line[:-1] + "\\\n")
            else:
                parts.append(line)
                if i < len(lines) - 1:
                    parts.append(" ")
        joined = "".join(parts).strip()
        return self._inline(joined)

    def _render_blockquote(self, block: list[str]) -> str:
        # Strip leading '>' from each line.
        # Insert blank lines between transitions so inner parser splits blocks properly.
        inner_lines: list[str] = []
        prev_was_deeper: bool | None = None

        for line in block:
            stripped = line.strip()
            if stripped.startswith(">"):
                content = stripped[1:]
                if content.startswith(" "):
                    content = content[1:]
                is_deeper = content.strip().startswith(">")
                # Insert blank line on transition between non-deeper and deeper content
                if prev_was_deeper is not None and prev_was_deeper != is_deeper:
                    inner_lines.append("")
                inner_lines.append(content)
                prev_was_deeper = is_deeper
            else:
                inner_lines.append(line)
                prev_was_deeper = False

        # Recursively parse inner content (pass source_path for image embedding)
        inner_parser = MarkdownParser(source_path=getattr(self, "_effective_source", None))
        inner_html = inner_parser.parse("\n".join(inner_lines))
        # Merge headings from inner parser
        self.headings.extend(inner_parser.headings)
        return f"<blockquote>\n{inner_html}\n</blockquote>"

    def _render_table(self, block: list[str]) -> str:
        header_row = block[0]
        separator_row = block[1]
        body_rows = block[2:]

        headers = self._parse_table_row(header_row)
        alignments = self._parse_separator_row(separator_row)

        # Pad alignments to match header count
        while len(alignments) < len(headers):
            alignments.append("left")

        html = ["<table>", "<thead>", "<tr>"]
        for i, cell in enumerate(headers):
            align = alignments[i] if i < len(alignments) else "left"
            html.append(f'<th style="text-align:{align}">{self._inline(cell.strip())}</th>')
        html.append("</tr>")
        html.append("</thead>")

        if body_rows:
            html.append("<tbody>")
            for row_line in body_rows:
                cells = self._parse_table_row(row_line)
                html.append("<tr>")
                for i, cell in enumerate(cells):
                    align = alignments[i] if i < len(alignments) else "left"
                    html.append(f'<td style="text-align:{align}">{self._inline(cell.strip())}</td>')
                html.append("</tr>")
            html.append("</tbody>")

        html.append("</table>")
        return "\n".join(html)

    def _parse_table_row(self, line: str) -> list[str]:
        line = line.strip()
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]
        return line.split("|")

    def _parse_separator_row(self, line: str) -> list[str]:
        cells = self._parse_table_row(line)
        alignments: list[str] = []
        for cell in cells:
            cell = cell.strip()
            if cell.startswith(":") and cell.endswith(":"):
                alignments.append("center")
            elif cell.endswith(":"):
                alignments.append("right")
            else:
                alignments.append("left")
        return alignments

    def _render_list(self, block: list[str], ordered: bool) -> str:
        tag = "ol" if ordered else "ul"
        html = self._render_list_items(block, ordered)
        return f"<{tag}>{html}</{tag}>"

    def _render_list_items(self, lines: list[str], ordered: bool) -> str:
        """
        Render list items supporting nesting. Returns inner HTML (the <li> elements).
        """
        result: list[str] = []
        i = 0

        while i < len(lines):
            line = lines[i]
            # Match list item
            m = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)", line)
            if not m:
                # Continuation line — append to previous item
                if result:
                    # Remove the closing </li> and add the text
                    last = result.pop()
                    last = last.rstrip("</li>").rstrip()
                    result.append(last + " " + line.strip() + "</li>")
                i += 1
                continue

            indent = len(m.group(1))
            bullet = m.group(2)
            text = m.group(3)

            # Task list detection
            task_m = re.match(r"^\[([ xX])\]\s+(.*)", text)
            if task_m:
                checked = task_m.group(1).lower() == "x"
                task_text = task_m.group(2)
                checkbox = '<input type="checkbox" disabled checked>' if checked else '<input type="checkbox" disabled>'
                item_text = f"{checkbox} {self._inline(task_text)}"
            else:
                item_text = self._inline(text)

            # Collect nested lines (next lines with greater indentation)
            nested: list[str] = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                next_m = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)", next_line)
                if next_m:
                    next_indent = len(next_m.group(1))
                    if next_indent > indent:
                        nested.append(next_line)
                        j += 1
                    else:
                        break
                elif next_line.startswith(" " * (indent + 2)) or (indent == 0 and next_line.startswith("  ")):
                    nested.append(next_line)
                    j += 1
                else:
                    break

            if nested:
                # Determine if nested is ordered or unordered
                nested_first = nested[0].strip()
                nested_ordered = bool(re.match(r"\d+\.\s", nested_first))
                nested_tag = "ol" if nested_ordered else "ul"
                nested_html = self._render_list_items(nested, nested_ordered)
                result.append(f"<li>{item_text}<{nested_tag}>{nested_html}</{nested_tag}></li>")
            else:
                result.append(f"<li>{item_text}</li>")

            i = j

        return "".join(result)

    # ------------------------------------------------------------------
    # Helpers / detectors
    # ------------------------------------------------------------------

    def _is_hr(self, line: str) -> bool:
        """Return True if *line* is a horizontal rule."""
        for char in ("-", "*", "_"):
            if re.match(rf"^[{re.escape(char)}\s]{{3,}}$", line) and line.replace(" ", "").replace(char, "") == "":
                chars = [c for c in line if c == char]
                if len(chars) >= 3:
                    return True
        return False

    def _is_table_row(self, line: str) -> bool:
        return "|" in line.strip()

    def _is_separator_row(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped.startswith("|") and "|" not in stripped:
            return False
        # Remove outer pipes
        inner = stripped
        if inner.startswith("|"):
            inner = inner[1:]
        if inner.endswith("|"):
            inner = inner[:-1]
        cells = inner.split("|")
        return all(re.match(r"^:?-+:?$", cell.strip()) for cell in cells if cell.strip())

    def _is_raw_html(self, line: str) -> bool:
        """Return True if the line should be passed through as raw HTML."""
        block_tags = (
            "div", "table", "p", "ul", "ol", "pre", "blockquote",
            "h1", "h2", "h3", "h4", "h5", "h6", "hr", "br",
            "section", "nav", "article", "header", "footer",
        )
        if line.startswith("</"):
            return True
        for tag in block_tags:
            if line.lower().startswith(f"<{tag}"):
                return True
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments and perform all validation.

    Returns a Namespace with:
      - files: list[Path]  — resolved, ordered list of matched .md files
      - output: Path       — resolved output path
      - title: str         — page title (output stem)
    """
    parser = argparse.ArgumentParser(
        prog="md_to_html.py",
        description="Bundle one or more Markdown files into a single styled HTML file.",
    )

    parser.add_argument(
        "glob",
        metavar="glob",
        help='Glob pattern matching .md files (e.g. "docs/*.md")',
    )

    parser.add_argument(
        "-o", "--output",
        metavar="PATH",
        default="output.html",
        help="Output HTML file path (default: ./output.html)",
    )

    parser.add_argument(
        "--order",
        metavar="FILE",
        nargs="+",
        help="Explicit ordered list of file paths, overriding the glob expansion order",
    )

    args = parser.parse_args()

    # --- Expand glob ----------------------------------------------------------
    raw_matches = glob_module.glob(args.glob, recursive=True)
    # Filter to .md files only and resolve to absolute paths
    matched_files: list[Path] = sorted(
        {Path(p).resolve() for p in raw_matches if Path(p).suffix.lower() == ".md"},
        key=lambda p: str(p),
    )
    # Preserve original glob order (glob.glob returns in filesystem order)
    # Re-expand to keep original ordering rather than sorted set
    ordered_matches: list[Path] = []
    seen: set[Path] = set()
    for p in raw_matches:
        resolved = Path(p).resolve()
        if resolved.suffix.lower() == ".md" and resolved not in seen:
            ordered_matches.append(resolved)
            seen.add(resolved)

    if not ordered_matches:
        print(
            f"Error: glob pattern {args.glob!r} matched zero .md files.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Handle --order override ----------------------------------------------
    if args.order is not None:
        reordered: list[Path] = []
        matched_set = set(ordered_matches)
        for raw_path in args.order:
            resolved = Path(raw_path).resolve()
            if resolved not in matched_set:
                print(
                    f"Error: --order path {raw_path!r} is not in the set of files "
                    f"matched by the glob pattern.",
                    file=sys.stderr,
                )
                sys.exit(1)
            reordered.append(resolved)
        final_files = reordered
    else:
        final_files = ordered_matches

    # --- Validate output path -------------------------------------------------
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path = output_path.resolve()

    if not output_path.parent.exists():
        print(
            f"Error: output directory {str(output_path.parent)!r} does not exist.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Build result ---------------------------------------------------------
    title = output_path.stem
    args.files = final_files
    args.output = output_path
    args.title = title

    return args


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    print("Resolved files:")
    for f in args.files:
        print(f"  {f}")
    print(f"Output: {args.output}")
    print(f"Title:  {args.title}")


if __name__ == "__main__":
    main()
