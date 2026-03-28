"""
md2pdf.py — Markdown to PDF Converter

A single-file, self-contained Python CLI script that converts a Markdown (.md)
file into a PDF file using wkhtmltopdf.

Requirements: Python 3.11+, stdlib only.
"""
from __future__ import annotations

import argparse
import base64
import html
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Theme Assets — inlined CSS (to be filled by STORY-014)
# ---------------------------------------------------------------------------

STYLES: str = """
/* ── Reset & Custom Properties ─────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:           #ffffff;
  --text:         #1a1a1a;
  --muted:        #555555;
  --link:         #0066cc;
  --border:       #d0d0d0;
  --code-bg:      #f5f5f5;
  --code-text:    #333333;
  --pre-bg:       #f8f8f8;
  --table-head:   #f0f0f0;
  --table-alt:    #fafafa;
  --bq-border:    #0066cc;
  --bq-bg:        #f0f4ff;
  --hr-color:     #cccccc;
}

/* ── Layout ─────────────────────────────────────────────────────────────── */
html { font-size: 16px; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, sans-serif;
  line-height: 1.6;
  padding: 1rem;
}

.page-wrapper {
  display: flex;
  flex-direction: row;
  gap: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

article {
  flex: 1 1 0;
  min-width: 0;
  max-width: 860px;
}

/* ── Table of Contents Sidebar ──────────────────────────────────────────── */
#toc {
  flex: 0 0 220px;
  width: 220px;
  font-size: 0.875rem;
  color: var(--muted);
}

#toc a {
  color: var(--muted);
  text-decoration: none;
  display: block;
  padding: 0.15rem 0;
}

#toc a:hover { color: var(--link); }

#toc ul { list-style: none; padding-left: 0; }
#toc ul ul { padding-left: 1rem; }

/* ── Typography ─────────────────────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6 {
  margin: 1.5rem 0 0.5rem;
  line-height: 1.3;
  color: var(--text);
}

h1 { font-size: 2rem; }
h2 { font-size: 1.5rem; border-bottom: 1px solid var(--border); padding-bottom: 0.25rem; }
h3 { font-size: 1.25rem; }
h4 { font-size: 1.1rem; }
h5 { font-size: 1rem; }
h6 { font-size: 0.9rem; color: var(--muted); }

p { margin: 0.75rem 0; }

a { color: var(--link); }

/* ── Inline Code ────────────────────────────────────────────────────────── */
code {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 0.9em;
  background: var(--code-bg);
  color: var(--code-text);
  padding: 0.1em 0.35em;
  border-radius: 3px;
}

/* ── Code Blocks ────────────────────────────────────────────────────────── */
pre {
  background: var(--pre-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 1rem;
  overflow-x: auto;
  margin: 1rem 0;
  page-break-inside: avoid;
}

pre code {
  background: none;
  padding: 0;
  font-size: 0.9rem;
  color: var(--code-text);
  border-radius: 0;
}

/* ── Tables ─────────────────────────────────────────────────────────────── */
table {
  border-collapse: collapse;
  width: 100%;
  margin: 1rem 0;
  font-size: 0.95rem;
  page-break-inside: avoid;
}

th, td {
  border: 1px solid var(--border);
  padding: 0.5rem 0.75rem;
  text-align: left;
}

th { background: var(--table-head); font-weight: 600; }

tr:nth-child(even) td { background: var(--table-alt); }

/* ── Blockquotes ────────────────────────────────────────────────────────── */
blockquote {
  border-left: 4px solid var(--bq-border);
  background: var(--bq-bg);
  margin: 1rem 0;
  padding: 0.75rem 1rem;
  color: var(--muted);
  border-radius: 0 4px 4px 0;
}

blockquote p { margin: 0; }

/* ── Horizontal Rule ────────────────────────────────────────────────────── */
hr {
  border: none;
  border-top: 2px solid var(--hr-color);
  margin: 2rem 0;
}

/* ── Lists ──────────────────────────────────────────────────────────────── */
ul, ol { padding-left: 1.75rem; margin: 0.5rem 0; }
li { margin: 0.25rem 0; }

/* ── Images ─────────────────────────────────────────────────────────────── */
img { max-width: 100%; height: auto; border-radius: 4px; }

/* ── Print / PDF ────────────────────────────────────────────────────────── */
@media print {
  body {
    margin: 0;
    padding: 0;
    background: #ffffff;
    color: #000000;
  }

  .page-wrapper {
    display: flex;
    flex-direction: row;
    gap: 1.5rem;
    max-width: 100%;
    margin: 0;
  }

  a {
    color: #0066cc;
    text-decoration: none;
  }

  pre, table {
    page-break-inside: avoid;
  }

  h1, h2, h3, h4, h5, h6 {
    page-break-after: avoid;
  }
}
"""

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

# Inline-level regexes (Phase 2)
_RE_INLINE_CODE = re.compile(r'`([^`]+)`')
_RE_IMAGE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
_RE_LINK = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
_RE_BOLD_STAR = re.compile(r'\*\*(.+?)\*\*', re.DOTALL)
_RE_BOLD_UNDER = re.compile(r'__(.+?)__', re.DOTALL)
_RE_ITALIC_STAR = re.compile(r'\*(.+?)\*', re.DOTALL)
_RE_ITALIC_UNDER = re.compile(r'_(.+?)_', re.DOTALL)
_RE_STRIKETHROUGH = re.compile(r'~~(.+?)~~', re.DOTALL)


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


def inline_parse(text: str, base_dir: Path) -> str:
    """Parse and render inline Markdown constructs to HTML.

    Processing order (prevents double-substitution):
      1. Inline code spans extracted to placeholders (content frozen).
      2. Images extracted to placeholders (embed_image called on src).
      3. Links extracted to placeholders (label recursively parsed).
      4. Remaining & < > HTML-escaped.
      5. Bold (**text** / __text__) → <strong>.
      6. Italic (*text* / _text_) → <em>.
      7. Strikethrough (~~text~~) → <del>.
      8. Placeholders restored.

    Args:
        text:     Raw inline Markdown text.
        base_dir: Base directory for resolving local image paths.

    Returns:
        HTML string with inline constructs rendered.
    """
    placeholders: dict[str, str] = {}
    _ph = [0]

    def _store(html_fragment: str) -> str:
        key = f'\x00{_ph[0]}\x00'
        _ph[0] += 1
        placeholders[key] = html_fragment
        return key

    # 1. Extract inline code spans (content is HTML-escaped, not further parsed).
    def _repl_code(m: re.Match) -> str:
        return _store(f'<code>{html.escape(m.group(1))}</code>')

    text = _RE_INLINE_CODE.sub(_repl_code, text)

    # 2. Extract images (before HTML-escaping so src is still raw).
    def _repl_image(m: re.Match) -> str:
        alt = m.group(1)
        src = m.group(2)
        final_src = embed_image(src, base_dir)
        return _store(f'<img alt="{html.escape(alt)}" src="{html.escape(final_src)}">')

    text = _RE_IMAGE.sub(_repl_image, text)

    # 3. Extract links (before HTML-escaping so url is still raw).
    def _repl_link(m: re.Match) -> str:
        label = m.group(1)
        url = m.group(2)
        parsed_label = inline_parse(label, base_dir)
        return _store(f'<a href="{html.escape(url)}">{parsed_label}</a>')

    text = _RE_LINK.sub(_repl_link, text)

    # 4. HTML-escape remaining & < > (placeholder chars \x00 are unaffected).
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # 5. Bold (**text** before *text* to avoid partial match).
    text = _RE_BOLD_STAR.sub(r'<strong>\1</strong>', text)
    text = _RE_BOLD_UNDER.sub(r'<strong>\1</strong>', text)

    # 6. Italic (single * or _, remaining after bold consumed **).
    text = _RE_ITALIC_STAR.sub(r'<em>\1</em>', text)
    text = _RE_ITALIC_UNDER.sub(r'<em>\1</em>', text)

    # 7. Strikethrough.
    text = _RE_STRIKETHROUGH.sub(r'<del>\1</del>', text)

    # 8. Restore all placeholders (code, images, links).
    for key, value in placeholders.items():
        text = text.replace(key, value)

    return text


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
        inline_text = inline_parse(raw_text, self._base_dir)
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

        inner = inline_parse(' '.join(bq_lines), self._base_dir)
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
            item_text = inline_parse(item_text, self._base_dir)

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
            out.append(f'<th{style}>{inline_parse(cell, self._base_dir)}</th>')
        out.append('</tr></thead>')

        # Body
        out.append('<tbody>')
        for row_line in body_rows:
            cells = split_row(row_line)
            out.append('<tr>')
            for i, cell in enumerate(cells):
                align = alignments[i] if i < len(alignments) else ''
                style = f' style="text-align: {align}"' if align else ''
                out.append(f'<td{style}>{inline_parse(cell, self._base_dir)}</td>')
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
        inner = inline_parse(text, self._base_dir)
        self._html_parts.append(f'<p>{inner}</p>')


# ---------------------------------------------------------------------------
# Pipeline stubs (to be implemented in subsequent stories)
# ---------------------------------------------------------------------------


def convert(markdown_text: str, base_dir: Path) -> ParseResult:
    """Parse Markdown text into a ParseResult (block + inline parsing).

    Block elements (headings, code blocks, blockquotes, lists, tables,
    horizontal rules, paragraphs) are fully parsed. Inline formatting
    (bold, italic, strikethrough, inline code, links, images) is also
    applied via inline_parse().

    Args:
        markdown_text: Raw Markdown source string.
        base_dir:      Directory of the input file (used for image embedding).

    Returns:
        ParseResult with body_html, headings (H1–H3), and title (first H1 text).
    """
    lines = markdown_text.splitlines()
    parser = _BlockParser(lines, base_dir)
    return parser.parse()


def build_toc(headings: list[Heading]) -> str:
    """Build an HTML table-of-contents <nav> element from a list of headings.

    Only H1–H3 headings are included. H1 → top-level list items; H2 → one
    level of nesting; H3 → two levels of nesting. Level jumps (e.g. H1
    directly followed by H3) are handled gracefully — the output is always
    well-nested HTML. Returns an empty string when *headings* contains no
    H1–H3 entries.

    Slugs are taken directly from Heading.slug — not re-generated here.

    Args:
        headings: Ordered list of Heading objects (H1–H3 from ParseResult).

    Returns:
        An HTML string for the ToC ``<nav id="toc">`` element, or ``""`` if
        there are no H1–H3 headings to display.
    """
    # Filter to H1–H3 only (ToC scope).
    toc_headings = [h for h in headings if 1 <= h.level <= 3]
    if not toc_headings:
        return ""

    parts: list[str] = []
    parts.append('<nav id="toc">')

    # Stack tracks the heading levels of currently-open <ul> elements.
    stack: list[int] = []

    for heading in toc_headings:
        level = heading.level

        if not stack:
            # First item: open a <ul> at this level.
            parts.append("<ul>")
            stack.append(level)
        elif level > stack[-1]:
            # Deeper level: open exactly ONE new <ul>, regardless of jump size.
            # (H1 → H3 still produces one nested <ul>, keeping HTML valid.)
            parts.append("<ul>")
            stack.append(level)
        elif level < stack[-1]:
            # Shallower level: close <li>/<ul> pairs until at or below target.
            while stack and stack[-1] > level:
                parts.append("</li></ul>")
                stack.pop()
            if not stack:
                # Went past root — open a fresh <ul>.
                parts.append("<ul>")
                stack.append(level)
            else:
                # Close the previous sibling <li> (same level now).
                parts.append("</li>")
        else:
            # Same level: just close the previous sibling <li>.
            parts.append("</li>")

        # Open the new list item (left open for potential child <ul>).
        parts.append(f'<li><a href="#{heading.slug}">{heading.text}</a>')

    # Close all open <li> and <ul> elements.
    while stack:
        parts.append("</li></ul>")
        stack.pop()

    parts.append("</nav>")
    return "".join(parts)


def render_page(result: ParseResult, title: str | None, toc_html: str) -> str:
    """Assemble and return a complete HTML5 document string for PDF rendering.

    Combines *result.body_html*, *toc_html*, the page *title*, and the
    ``STYLES`` module constant into a valid HTML5 document. The document is
    self-contained (no external stylesheets or scripts) and suitable for
    passing to ``wkhtmltopdf``.

    Args:
        result:   ParseResult with converted body HTML.
        title:    The resolved page title string (HTML-escaped in output).
        toc_html: Pre-rendered ToC ``<nav id="toc">`` HTML, or ``""`` to
                  suppress the sidebar entirely.

    Returns:
        A complete HTML5 document as a string.
    """
    safe_title = html.escape(title or "")

    # ── <head> ────────────────────────────────────────────────────────────
    head = (
        f"<head>"
        f"<meta charset=\"UTF-8\">"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
        f"<title>{safe_title}</title>"
        f"<style>{STYLES}</style>"
        f"</head>"
    )

    # ── ToC sidebar (conditional) ──────────────────────────────────────────
    sidebar = f"<aside id=\"toc-sidebar\">{toc_html}</aside>" if toc_html else ""

    # ── <body> ────────────────────────────────────────────────────────────
    body = (
        f"<body>"
        f"<main>"
        f"<div class=\"page-wrapper\">"
        f"<article>{result.body_html}</article>"
        f"{sidebar}"
        f"</div>"
        f"</main>"
        f"</body>"
    )

    return f"<!DOCTYPE html><html lang=\"en\">{head}{body}</html>"


def export_pdf(html_content: str, output_path: Path) -> None:
    """Export HTML content to a PDF using wkhtmltopdf.

    Writes *html_content* to a temporary file, then invokes wkhtmltopdf to
    render it as a PDF at *output_path*.  The temporary file is deleted in a
    ``finally`` block regardless of success or failure.

    Args:
        html_content: Complete HTML document string (UTF-8).
        output_path:  Destination path for the generated PDF.

    Raises:
        SystemExit(1): If wkhtmltopdf exits with a non-zero return code.
    """
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
            tmp_path = f.name
            f.write(html_content)

        cmd = [
            "wkhtmltopdf",
            "--page-size", "A4",
            "--margin-top", "20mm",
            "--margin-right", "20mm",
            "--margin-bottom", "20mm",
            "--margin-left", "20mm",
            "--enable-internal-links",
            "--enable-local-file-access",
            tmp_path,
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            sys.stderr.buffer.write(result.stderr)
            sys.exit(1)
    finally:
        if tmp_path is not None:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass


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
    """Orchestrate the full Markdown → PDF pipeline."""
    check_wkhtmltopdf()
    args = parse_args()

    # Read input Markdown file
    try:
        markdown_text = args.input.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: cannot read input file: {exc}", file=sys.stderr)
        sys.exit(1)

    # Convert Markdown to HTML fragments + metadata
    result = convert(markdown_text, base_dir=args.input.parent)

    # Resolve title: CLI flag > first H1 > input file stem
    title = args.title or result.title or args.input.stem

    # Build table of contents
    toc_html = build_toc(result.headings)

    # Assemble full HTML document
    page_html = render_page(result, title, toc_html)

    # Invoke wkhtmltopdf
    export_pdf(page_html, args.output)

    print(f"Written: {args.output}")


if __name__ == "__main__":
    main()
