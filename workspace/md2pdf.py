"""
md2pdf.py — Markdown to PDF Converter

A single-file, self-contained Python CLI script that converts a Markdown (.md)
file into a PDF file using wkhtmltopdf.

Requirements: Python 3.11+, stdlib only.
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Theme Assets — inlined CSS (to be filled by STORY-014)
# ---------------------------------------------------------------------------

STYLES: str = ""

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class Heading:
    """Represents a heading extracted from the Markdown document."""

    level: int
    text: str
    slug: str


@dataclass
class ParseResult:
    """Result of parsing a Markdown document."""

    body_html: str
    headings: list[Heading]
    title: str | None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Returns a Namespace with:
        - input: Path  — validated path to an existing .md file
        - output: Path — output PDF path (defaults to <input-stem>.pdf
                         in the same directory as the input)
        - title: str | None — optional title override
    """
    parser = argparse.ArgumentParser(
        prog="md2pdf",
        description="Convert a Markdown file to a PDF document.",
    )
    parser.add_argument(
        "input",
        metavar="INPUT",
        help="Path to the input Markdown (.md) file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT",
        default=None,
        help="Output PDF file path. Defaults to <input-stem>.pdf in the same directory.",
    )
    parser.add_argument(
        "-t",
        "--title",
        metavar="TITLE",
        default=None,
        help="Override the document title used in HTML <title> and the top heading.",
    )

    args = parser.parse_args(argv)

    # Validate the input path
    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(f"Input file does not exist: {args.input}")
    if not input_path.is_file():
        parser.error(f"Input path is not a file: {args.input}")
    if input_path.suffix.lower() != ".md":
        parser.error(f"Input file must have a .md extension: {args.input}")

    args.input = input_path

    # Resolve output path
    if args.output is None:
        args.output = input_path.parent / (input_path.stem + ".pdf")
    else:
        args.output = Path(args.output)

    return args


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


def _inline_stub(text: str, _base_dir: Path) -> str:
    """Phase-1 inline processing: HTML-escape only, no inline formatting.

    Phase 2 (STORY-012) will replace this with full inline_parse().
    """
    return html.escape(text)


# ---------------------------------------------------------------------------
# Block parser
# ---------------------------------------------------------------------------


class _BlockParser:
    """State-machine block parser for Markdown → HTML conversion."""

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
# Pipeline stubs (to be implemented in subsequent stories)
# ---------------------------------------------------------------------------


def convert(markdown_text: str, base_dir: Path) -> ParseResult:
    """Parse Markdown text into a ParseResult (Phase 1: block-level parsing).

    Block elements (headings, code blocks, blockquotes, lists, tables,
    horizontal rules, paragraphs) are fully parsed. Inline formatting is
    HTML-escaped only (Phase 2 in STORY-012 will add full inline rendering).

    Args:
        markdown_text: Raw Markdown source string.
        base_dir:      Directory of the input file (reserved for Phase 2 image embedding).

    Returns:
        ParseResult with body_html, headings (H1–H3), and title (first H1 text).
    """
    lines = markdown_text.splitlines()
    parser = _BlockParser(lines, base_dir)
    return parser.parse()


def build_toc(headings: list[Heading]) -> str:
    """Build an HTML table-of-contents from a list of headings."""
    raise NotImplementedError


def render_page(result: ParseResult, title: str | None, toc_html: str) -> str:
    """Render the full HTML page from a ParseResult."""
    raise NotImplementedError


def embed_image(src: str, base_dir: Path) -> str:
    """Embed an image as a base64 data URI."""
    raise NotImplementedError


def export_pdf(html_content: str, output_path: Path) -> None:
    """Export HTML content to a PDF using wkhtmltopdf."""
    raise NotImplementedError


def check_wkhtmltopdf() -> None:
    """Verify wkhtmltopdf is available on PATH; exit with an error if not.

    If wkhtmltopdf is found, returns None silently.
    If not found, prints a human-readable installation guide to stderr and exits 1.
    """
    if shutil.which("wkhtmltopdf") is not None:
        return None

    print(
        "Error: wkhtmltopdf is not installed or not found on PATH.\n"
        "\n"
        "md2pdf requires wkhtmltopdf to render HTML to PDF.\n"
        "A modern release (>= 0.12.x) is required for clickable internal PDF links.\n"
        "\n"
        "Installation instructions:\n"
        "\n"
        "  macOS:\n"
        "    brew install wkhtmltopdf\n"
        "\n"
        "  Linux (Debian/Ubuntu):\n"
        "    sudo apt-get install wkhtmltopdf\n"
        "    For other distros, visit: https://wkhtmltopdf.org/downloads.html\n"
        "\n"
        "  Windows:\n"
        "    Download the installer from: https://wkhtmltopdf.org/downloads.html\n",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point — stub pipeline (no PDF written yet)."""
    check_wkhtmltopdf()
    args = parse_args()
    print(f"[md2pdf] Input:  {args.input}")
    print(f"[md2pdf] Output: {args.output}")
    if args.title:
        print(f"[md2pdf] Title:  {args.title}")
    print("[md2pdf] Pipeline not yet implemented.")


if __name__ == "__main__":
    main()
