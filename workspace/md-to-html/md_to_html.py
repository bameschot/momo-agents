"""
md_to_html.py — Markdown to HTML Bundler

A single-file, self-contained Python CLI script that accepts a glob pattern
matching one or more Markdown files and bundles them into a single styled HTML file.

Requirements: Python 3.11+, stdlib only.
"""

from __future__ import annotations

import argparse
import glob as glob_module
import sys
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
