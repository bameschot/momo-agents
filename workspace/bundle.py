"""bundle.py — packages the project workspace into a named zip file.

Usage:
    python bundle.py [project_root] [--output <output_dir>]

The zip file is named after the most recently modified design document found in
<project_root>/design/, with all extensions stripped (e.g. my-feature.new.md → my-feature.zip).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Exclusion rules
# ---------------------------------------------------------------------------

EXCLUDED_DIRS = {".git", "__pycache__", "node_modules"}
EXCLUDED_FILES = {".env"}
EXCLUDED_SUFFIXES = {".pyc"}


def is_excluded(path: Path, root: Path) -> bool:
    """Return True if *path* should be omitted from the zip archive."""
    # TODO: implement exclusion logic
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def resolve_zip_name(project_root: Path) -> str:
    """Return the stem (all extensions stripped) of the last-modified .md file
    found inside <project_root>/design/.

    Raises SystemExit with a clear message when no .md files are found.
    """
    # TODO: implement
    raise NotImplementedError


def create_bundle(project_root: Path, output_dir: Path, zip_name: str) -> Path:
    """Walk *project_root* recursively, apply exclusions, and write a zip archive.

    Returns the Path of the created zip file.
    """
    # TODO: implement
    raise NotImplementedError


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and return CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Bundle the project workspace into a zip file.",
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=None,
        help="Root of the workspace to bundle (default: directory containing this script).",
    )
    parser.add_argument(
        "--output",
        metavar="OUTPUT_DIR",
        default=None,
        help="Directory where the zip file is written (default: current working directory).",
    )
    return parser.parse_args(argv)


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """Resolve and validate project_root and output_dir.

    - project_root defaults to the directory containing this script
    - output_dir defaults to the current working directory
    - Validates that project_root exists and is a directory
    - Creates output_dir if it doesn't exist
    - Exits with error message if project_root is invalid

    Returns a tuple (project_root, output_dir).
    """
    # Resolve project_root
    if args.project_root is None:
        project_root = Path(__file__).parent
    else:
        project_root = Path(args.project_root)

    # Validate project_root
    if not project_root.exists() or not project_root.is_dir():
        sys.stderr.write(
            f"Error: project_root '{project_root}' does not exist or is not a directory\n"
        )
        sys.exit(2)

    # Resolve output_dir
    if args.output is None:
        output_dir = Path.cwd()
    else:
        output_dir = Path(args.output)

    # Create output_dir if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    return project_root, output_dir


def main(argv: list[str] | None = None) -> None:
    """Entry point."""
    args = parse_args(argv)
    project_root, output_dir = resolve_paths(args)

    # TODO: resolve zip_name via resolve_zip_name()
    # TODO: create bundle via create_bundle()

    print(
        f"Bundle script ready: project_root={project_root}, output_dir={output_dir}"
    )


if __name__ == "__main__":
    main()
