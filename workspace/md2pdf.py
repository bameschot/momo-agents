"""
md2pdf.py — Markdown to PDF Converter

A single-file, self-contained Python CLI script that converts a Markdown (.md)
file into a PDF file using wkhtmltopdf.

Requirements: Python 3.11+, stdlib only.
"""
from __future__ import annotations

import argparse
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
# Pipeline stubs (to be implemented in subsequent stories)
# ---------------------------------------------------------------------------


def convert(source: str) -> ParseResult:
    """Parse Markdown source into a ParseResult."""
    raise NotImplementedError


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
