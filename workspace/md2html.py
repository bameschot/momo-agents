"""
md2html.py — Markdown to HTML Converter

A single-file, self-contained Python CLI script that converts a Markdown (.md)
file into a fully self-contained HTML file (CSS, JS, and images inlined).

Requirements: Python 3.11+, stdlib only.
"""
from __future__ import annotations

import argparse
import base64
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Module-level constants (placeholders for later stories)
# ---------------------------------------------------------------------------

# CSS string inlined into the output HTML (populated by a later story)
CSS: str = ""

# JavaScript string inlined into the output HTML (populated by a later story)
JS: str = ""

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class Heading:
    """Represents a single heading extracted from the Markdown document."""

    level: int   # 1–6
    text: str    # Plain text of the heading (no HTML)
    slug: str    # URL-safe id attribute value (e.g. "my-heading")


@dataclass
class ParseResult:
    """Result of converting Markdown text to HTML."""

    body_html: str              # Converted HTML body fragment
    headings: list[Heading]     # Ordered list of headings for ToC generation
    title: str | None           # First H1 text, if any; otherwise None


# ---------------------------------------------------------------------------
# Compiled regexes (module-level for performance)
# ---------------------------------------------------------------------------

_RE_ATX_HEADING = re.compile(r'^(#{1,6})\s+(.*)')
_RE_FENCED_FENCE = re.compile(r'^(`{3,})(.*)')
_RE_BLOCKQUOTE = re.compile(r'^>\s?(.*)')
_RE_UNORDERED_ITEM = re.compile(r'^( *)([-*+])\s+(.*)')
_RE_ORDERED_ITEM = re.compile(r'^( *)(\d+)\.\s+(.*)')
_RE_TABLE_SEP = re.compile(r'^\|?[\s]*:?-+:?[\s]*(\|[\s]*:?-+:?[\s]*)*\|?$')
_RE_HR = re.compile(r'^(\*{3,}|-{3,}|_{3,})\s*$')
_RE_SLUG_STRIP = re.compile(r'[^a-z0-9\-]')
_RE_SLUG_SPACES = re.compile(r'\s+')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    """Convert heading text to a URL-safe slug.

    Lowercase, spaces→hyphens, strip non-alphanumeric-hyphen characters.
    """
    text = text.lower()
    text = _RE_SLUG_SPACES.sub('-', text)
    text = _RE_SLUG_STRIP.sub('', text)
    return text


def _inline_stub(text: str, base_dir: Path) -> str:  # noqa: ARG001
    """Identity stub for inline processing (replaced by STORY-004)."""
    return text


# ---------------------------------------------------------------------------
# Block parser
# ---------------------------------------------------------------------------


class _BlockParser:
    """State-machine block parser."""

    def __init__(self, lines: list[str], base_dir: Path) -> None:
        self._lines = lines
        self._base_dir = base_dir
        self._pos = 0

        self._html_parts: list[str] = []
        self._headings: list[Heading] = []
        self._title: str | None = None
        self._slug_counts: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Main parsing entry point
    # ------------------------------------------------------------------

    def parse(self) -> ParseResult:
        while self._pos < len(self._lines):
            line = self._lines[self._pos]

            # Skip blank lines between blocks
            if not line.strip():
                self._pos += 1
                continue

            # Fenced code block
            m_fence = _RE_FENCED_FENCE.match(line)
            if m_fence:
                self._parse_fenced_code(m_fence)
                continue

            # ATX heading
            m_heading = _RE_ATX_HEADING.match(line)
            if m_heading:
                self._parse_heading(m_heading)
                continue

            # Horizontal rule (must come before list detection so `---` isn't confused)
            if _RE_HR.match(line):
                self._html_parts.append('<hr>')
                self._pos += 1
                continue

            # Blockquote
            if _RE_BLOCKQUOTE.match(line):
                self._parse_blockquote()
                continue

            # Unordered list
            if _RE_UNORDERED_ITEM.match(line):
                self._parse_list(ordered=False)
                continue

            # Ordered list
            if _RE_ORDERED_ITEM.match(line):
                self._parse_list(ordered=True)
                continue

            # Table (detect by pipe + separator on next non-empty line)
            if '|' in line and self._is_table_start():
                self._parse_table()
                continue

            # Paragraph (fallthrough)
            self._parse_paragraph()

        body_html = '\n'.join(self._html_parts)
        return ParseResult(body_html=body_html, headings=self._headings, title=self._title)

    # ------------------------------------------------------------------
    # Slug helpers
    # ------------------------------------------------------------------

    def _make_slug(self, text: str) -> str:
        base = slugify(text)
        if base not in self._slug_counts:
            self._slug_counts[base] = 1
            return base
        self._slug_counts[base] += 1
        return f"{base}-{self._slug_counts[base]}"

    # ------------------------------------------------------------------
    # Block parsers
    # ------------------------------------------------------------------

    def _parse_heading(self, m: re.Match) -> None:
        hashes = m.group(1)
        level = len(hashes)
        raw_text = m.group(2).strip()
        slug = self._make_slug(raw_text)
        inline_text = _inline_stub(raw_text, self._base_dir)
        self._html_parts.append(f'<h{level} id="{slug}">{inline_text}</h{level}>')

        if level <= 3:
            heading = Heading(level=level, text=raw_text, slug=slug)
            self._headings.append(heading)
            if level == 1 and self._title is None:
                self._title = raw_text

        self._pos += 1

    def _parse_fenced_code(self, m: re.Match) -> None:
        fence_chars = m.group(1)   # e.g. '```'
        lang = m.group(2).strip()
        self._pos += 1  # skip opening fence

        code_lines: list[str] = []
        while self._pos < len(self._lines):
            line = self._lines[self._pos]
            if line.startswith(fence_chars):
                self._pos += 1  # skip closing fence
                break
            code_lines.append(line)
            self._pos += 1

        code_content = html.escape('\n'.join(code_lines))
        if lang:
            self._html_parts.append(
                f'<pre><code class="language-{lang}">{code_content}</code></pre>'
            )
        else:
            self._html_parts.append(f'<pre><code>{code_content}</code></pre>')

    def _parse_blockquote(self) -> None:
        bq_lines: list[str] = []
        while self._pos < len(self._lines):
            line = self._lines[self._pos]
            m = _RE_BLOCKQUOTE.match(line)
            if m:
                bq_lines.append(m.group(1))
                self._pos += 1
            else:
                break

        inner = _inline_stub(' '.join(bq_lines), self._base_dir)
        self._html_parts.append(f'<blockquote><p>{inner}</p></blockquote>')

    def _parse_list(self, *, ordered: bool) -> None:
        """Parse a list (ordered or unordered), handling nesting via indentation."""
        regex = _RE_ORDERED_ITEM if ordered else _RE_UNORDERED_ITEM
        tag = 'ol' if ordered else 'ul'
        parts: list[str] = []

        # indent_stack holds indent (number of leading spaces) for each open level
        indent_stack: list[int] = []

        while self._pos < len(self._lines):
            line = self._lines[self._pos]
            if not line.strip():
                break  # blank line ends the list

            m = regex.match(line)
            if not m:
                break  # non-list line ends the list

            indent = len(m.group(1))
            item_text = m.group(3)
            item_text = _inline_stub(item_text, self._base_dir)

            if not indent_stack:
                # Open the first list
                parts.append(f'<{tag}>')
                indent_stack.append(indent)
            elif indent > indent_stack[-1]:
                # Deeper indent: open a nested list inside the last open li
                parts.append(f'<{tag}>')
                indent_stack.append(indent)
            elif indent < indent_stack[-1]:
                # Shallower indent: close lists until we match the level
                while len(indent_stack) > 1 and indent < indent_stack[-1]:
                    parts.append(f'</li></{tag}>')
                    indent_stack.pop()
                # Close the previous item at this level
                parts.append('</li>')
            else:
                # Same level: close previous item
                parts.append('</li>')

            parts.append(f'<li>{item_text}')
            self._pos += 1

        # Close all open lists
        while indent_stack:
            parts.append(f'</li></{tag}>')
            indent_stack.pop()

        self._html_parts.append(''.join(parts))

    def _is_table_start(self) -> bool:
        """Check if current position starts a table (pipe line followed by sep)."""
        next_pos = self._pos + 1
        while next_pos < len(self._lines):
            next_line = self._lines[next_pos].strip()
            if not next_line:
                return False
            return bool(_RE_TABLE_SEP.match(next_line))
        return False

    def _parse_table(self) -> None:
        """Parse a GFM table block."""
        table_lines: list[str] = []

        while self._pos < len(self._lines):
            line = self._lines[self._pos]
            if not line.strip():
                break
            if '|' not in line and not _RE_TABLE_SEP.match(line.strip()):
                break
            table_lines.append(line)
            self._pos += 1

        if len(table_lines) < 2:
            self._html_parts.append(f'<pre>{html.escape(chr(10).join(table_lines))}</pre>')
            return

        def split_row(row: str) -> list[str]:
            row = row.strip()
            if row.startswith('|'):
                row = row[1:]
            if row.endswith('|'):
                row = row[:-1]
            return [cell.strip() for cell in row.split('|')]

        header_cells = split_row(table_lines[0])
        sep_cells = split_row(table_lines[1])
        num_cols = len(header_cells)

        # Parse alignment from separator row
        alignments: list[str] = []
        for sep in sep_cells:
            s = sep.strip()
            if s.startswith(':') and s.endswith(':'):
                alignments.append('center')
            elif s.endswith(':'):
                alignments.append('right')
            elif s.startswith(':'):
                alignments.append('left')
            else:
                alignments.append('')

        # Validate column counts
        raw_block = '\n'.join(table_lines)
        if len(sep_cells) != num_cols:
            self._html_parts.append(f'<pre>{html.escape(raw_block)}</pre>')
            return

        body_rows = table_lines[2:]

        # Validate body rows column counts
        for row_line in body_rows:
            cells = split_row(row_line)
            if len(cells) != num_cols:
                self._html_parts.append(f'<pre>{html.escape(raw_block)}</pre>')
                return

        # Build table HTML
        out: list[str] = ['<table>']

        # Header
        out.append('<thead><tr>')
        for i, cell in enumerate(header_cells):
            align = alignments[i] if i < len(alignments) else ''
            style = f' style="text-align: {align}"' if align else ''
            out.append(f'<th{style}>{_inline_stub(cell, self._base_dir)}</th>')
        out.append('</tr></thead>')

        # Body
        out.append('<tbody>')
        for row_line in body_rows:
            cells = split_row(row_line)
            out.append('<tr>')
            for i, cell in enumerate(cells):
                align = alignments[i] if i < len(alignments) else ''
                style = f' style="text-align: {align}"' if align else ''
                out.append(f'<td{style}>{_inline_stub(cell, self._base_dir)}</td>')
            out.append('</tr>')
        out.append('</tbody>')

        out.append('</table>')
        self._html_parts.append(''.join(out))

    def _parse_paragraph(self) -> None:
        """Collect consecutive non-blank, non-special lines into a paragraph."""
        para_lines: list[str] = []

        while self._pos < len(self._lines):
            line = self._lines[self._pos]
            if not line.strip():
                break
            # Stop if this line would start a new block type
            if (
                _RE_ATX_HEADING.match(line)
                or _RE_FENCED_FENCE.match(line)
                or _RE_HR.match(line)
                or _RE_BLOCKQUOTE.match(line)
                or _RE_UNORDERED_ITEM.match(line)
                or _RE_ORDERED_ITEM.match(line)
                or ('|' in line and self._is_table_start())
            ):
                break
            para_lines.append(line)
            self._pos += 1

        text = ' '.join(para_lines)
        inner = _inline_stub(text, self._base_dir)
        self._html_parts.append(f'<p>{inner}</p>')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and validate command-line arguments.

    Returns an argparse.Namespace with the following attributes:
      - input:  pathlib.Path  — validated path to the input .md file
      - output: pathlib.Path  — path for the output .html file
      - title:  str | None    — override title, or None if not supplied
    """
    parser = argparse.ArgumentParser(
        prog="md2html.py",
        description="Convert a Markdown file to a self-contained HTML file.",
    )

    parser.add_argument(
        "input",
        metavar="input",
        type=Path,
        help="Path to the input Markdown (.md) file.",
    )

    parser.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT",
        type=Path,
        default=None,
        help=(
            "Path for the output HTML file. "
            "Defaults to <input-basename>.html in the same directory as the input."
        ),
    )

    parser.add_argument(
        "-t",
        "--title",
        metavar="TITLE",
        default=None,
        help=(
            "Override the HTML <title> and page heading. "
            "Defaults to the first H1 in the document, or the filename if none exists."
        ),
    )

    args = parser.parse_args(argv)

    # Validate that the input file exists and is a file.
    if not args.input.exists():
        parser.error(f"Input file not found: {args.input}")
    if not args.input.is_file():
        parser.error(f"Input path is not a file: {args.input}")

    # Compute default output path when -o is not supplied.
    if args.output is None:
        args.output = args.input.parent / (args.input.stem + ".html")

    return args


# ---------------------------------------------------------------------------
# Stub functions (to be implemented by later stories)
# ---------------------------------------------------------------------------


def convert(markdown_text: str, base_dir: Path) -> ParseResult:
    """Convert Markdown text to HTML (block-level pass).

    Inline processing is delegated to _inline_stub (identity) for now;
    STORY-004 will replace it with real inline parsing.

    Args:
        markdown_text: Raw Markdown source.
        base_dir:      Directory of the input file (used to resolve local images).

    Returns:
        A ParseResult with body_html, headings, and title.
    """
    lines = markdown_text.splitlines()
    parser = _BlockParser(lines, base_dir)
    return parser.parse()


def build_toc(headings: list[Heading]) -> str:
    """Build a Table of Contents HTML <nav> element from headings.

    Args:
        headings: Ordered list of Heading objects.

    Returns:
        An HTML string for the ToC navigation element.
    """
    # Stub — real implementation added in a later story.
    return ""


def render_page(result: ParseResult, title: str, toc_html: str) -> str:
    """Assemble and return a complete HTML5 document string.

    Args:
        result:   ParseResult with converted body HTML.
        title:    The page title string.
        toc_html: Pre-rendered ToC HTML.

    Returns:
        A complete HTML5 document as a string.
    """
    # Stub — real implementation added in a later story.
    return ""


def embed_image(src: str, base_dir: Path) -> str:
    """Return a data URI for a local image, or the original src for remote ones.

    - HTTP/HTTPS URLs are returned unchanged (no network request is made).
    - Local paths are resolved relative to *base_dir*, read as bytes, and
      encoded as a ``data:<mime>;base64,<data>`` string.
    - Unknown extensions or missing files emit a warning to stderr and return
      the original *src* unchanged.
    - This function never raises an exception.

    Args:
        src:      The image source (file path or URL).
        base_dir: Base directory for resolving relative local paths.

    Returns:
        A data URI string, or the original *src* if remote/missing/unknown.
    """
    # Extension → MIME type mapping (all supported image formats).
    _MIME_TYPES: dict[str, str] = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }

    # HTTP/HTTPS URLs — return as-is, no network request.
    if src.startswith(("http://", "https://")):
        return src

    # Resolve the path relative to base_dir.
    resolved = (base_dir / src).resolve()

    # Check for a supported extension.
    mime = _MIME_TYPES.get(resolved.suffix.lower())
    if mime is None:
        print(f"Warning: image not found: {src}", file=sys.stderr)
        return src

    # Check the file exists.
    if not resolved.exists():
        print(f"Warning: image not found: {src}", file=sys.stderr)
        return src

    # Encode as a Base64 data URI.
    try:
        data = base64.b64encode(resolved.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{data}"
    except OSError:
        print(f"Warning: image not found: {src}", file=sys.stderr)
        return src


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point — reads args and the input file; conversion is a stub."""
    args = parse_args()

    markdown_text = args.input.read_text(encoding="utf-8")

    # Placeholder — real conversion + HTML writing added in a later story.
    print(f"[md2html] Read {len(markdown_text)} bytes from {args.input}")
    print(f"[md2html] Output would be written to: {args.output}")
    if args.title:
        print(f"[md2html] Title override: {args.title}")


if __name__ == "__main__":
    main()
