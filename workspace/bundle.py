"""bundle.py — packages the project workspace into a named zip file.

Usage:
    python bundle-workspace.py [project_root] [--output <output_dir>]

The zip file is named after the most recently modified design document found in
<project_root>/design/, with all extensions stripped (e.g. my-feature.new.md → my-feature.zip).
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys
import zipfile
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Language exclusion data tables
# ---------------------------------------------------------------------------

LANGUAGE_EXCLUSIONS: dict[str, dict] = {
    "python": {
        "dirs":      frozenset({".venv", "venv", "__pycache__", ".pytest_cache",
                                 ".mypy_cache", ".ruff_cache", "dist", "build"}),
        "dir_globs": ("*.egg-info",),       # fnmatch patterns matched against dir name only
        "suffixes":  frozenset({".pyc"}),   # matched against file suffix (path.suffix)
        "rel_paths": (),                    # multi-segment prefix patterns (unused for python)
    },
    "javascript": {
        "dirs":      frozenset({"node_modules", "dist", "build", ".next", ".nuxt",
                                 ".cache", "coverage", ".parcel-cache", ".turbo"}),
        "dir_globs": (), "suffixes": frozenset(), "rel_paths": (),
    },
    "typescript": {
        "dirs":      frozenset({"node_modules", "dist", "build", ".next", ".nuxt",
                                 ".cache", "coverage", ".parcel-cache", ".turbo"}),
        "dir_globs": (), "suffixes": frozenset(), "rel_paths": (),
    },
    "java": {
        "dirs":      frozenset({"target", "build", ".gradle"}),
        "dir_globs": (), "suffixes": frozenset({".class", ".jar"}), "rel_paths": (),
    },
    "kotlin": {
        "dirs":      frozenset({"target", "build", ".gradle"}),
        "dir_globs": (), "suffixes": frozenset({".class"}), "rel_paths": (),
    },
    "rust": {
        "dirs":      frozenset({"target"}),
        "dir_globs": (), "suffixes": frozenset(), "rel_paths": (),
    },
    "go": {
        "dirs":      frozenset({"vendor", "bin"}),
        "dir_globs": (), "suffixes": frozenset(), "rel_paths": (),
    },
    "c": {
        "dirs":      frozenset({"build"}),
        "dir_globs": ("cmake-build-*",),
        "suffixes":  frozenset({".o", ".a", ".so", ".dll", ".exe"}),
        "rel_paths": (),
    },
    "cpp": {
        "dirs":      frozenset({"build"}),
        "dir_globs": ("cmake-build-*",),
        "suffixes":  frozenset({".o", ".a", ".so", ".dll", ".exe"}),
        "rel_paths": (),
    },
    "ruby": {
        "dirs":      frozenset({".bundle", "tmp", "log", "coverage"}),
        "dir_globs": (),
        "suffixes":  frozenset(),
        "rel_paths": ("vendor/bundle",),    # only vendor/bundle, not all of vendor/
    },
    "php": {
        "dirs":      frozenset({"vendor"}),
        "dir_globs": (),
        "suffixes":  frozenset(),
        "rel_paths": ("var/cache", "var/log"),
    },
    "csharp": {
        "dirs":      frozenset({"bin", "obj", ".vs", "packages"}),
        "dir_globs": (),
        "suffixes":  frozenset({".user"}),
        "rel_paths": (),
    },
}

ALIAS_MAP: dict[str, str] = {
    # canonical names (self-map)
    "python": "python", "javascript": "javascript", "typescript": "typescript",
    "java": "java", "kotlin": "kotlin", "rust": "rust", "go": "go",
    "c": "c", "cpp": "cpp", "ruby": "ruby", "php": "php", "csharp": "csharp",
    # aliases
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "kt": "kotlin",
    "rs": "rust",
    "golang": "go",
    "c++": "cpp",
    "cplusplus": "cpp",
    "c#": "csharp",
    "dotnet": "csharp",
    "cs": "csharp",
    "rb": "ruby",
}

# ---------------------------------------------------------------------------
# Exclusion rules
# ---------------------------------------------------------------------------

UNIVERSAL_DIRS: frozenset[str] = frozenset({".git"})


class ExclusionRules(NamedTuple):
    dir_names: frozenset[str]
    dir_globs: tuple[str, ...]
    file_suffixes: frozenset[str]
    rel_paths: tuple[str, ...]


def build_exclusion_rules(canonical_languages: list[str] | None) -> ExclusionRules:
    """Build an ExclusionRules instance from a list of canonical language names.

    When *canonical_languages* is None, unions all entries across all languages.
    Always adds the universal .git directory exclusion.
    """
    langs = list(LANGUAGE_EXCLUSIONS.keys()) if canonical_languages is None else canonical_languages
    dir_names: set[str] = set(UNIVERSAL_DIRS)
    dir_globs: list[str] = []
    file_suffixes: set[str] = set()
    rel_paths: list[str] = []
    for lang in langs:
        spec = LANGUAGE_EXCLUSIONS[lang]
        dir_names.update(spec["dirs"])
        dir_globs.extend(g for g in spec["dir_globs"] if g not in dir_globs)
        file_suffixes.update(spec["suffixes"])
        rel_paths.extend(p for p in spec["rel_paths"] if p not in rel_paths)
    return ExclusionRules(
        dir_names=frozenset(dir_names),
        dir_globs=tuple(dir_globs),
        file_suffixes=frozenset(file_suffixes),
        rel_paths=tuple(rel_paths),
    )


def should_exclude(path: Path, project_root: Path, rules: ExclusionRules) -> bool:
    """Return True if *path* should be omitted from the zip archive.

    Exclusion is determined by the provided *rules*:
    - A path component in rules.dir_names at any depth → excluded.
    - A directory-level component matching any pattern in rules.dir_globs → excluded.
    - A file whose suffix is in rules.file_suffixes → excluded.
    - A relative path whose string form starts with any entry in rules.rel_paths → excluded.
    """
    try:
        rel = path.relative_to(project_root)
    except ValueError:
        # Path is not relative to project_root; exclude it to be safe
        return True

    parts = rel.parts

    # Exact directory-name match at any depth
    if rules.dir_names & set(parts):
        return True

    # Glob match on any path component
    for part in parts:
        if any(fnmatch.fnmatch(part, pattern) for pattern in rules.dir_globs):
            return True

    # Multi-segment path prefix (normalise separators for cross-platform safety)
    rel_str = "/".join(parts)
    for rp in rules.rel_paths:
        if rel_str == rp or rel_str.startswith(rp + "/"):
            return True

    # File suffix
    if path.suffix in rules.file_suffixes:
        return True

    return False


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def resolve_zip_name(project_root: Path) -> str:
    """Return the stem (all extensions stripped) of the last-modified .md file
    found inside <project_root>/design/.

    Raises SystemExit with a clear message when no .md files are found.
    """
    design_dir = project_root / "design"

    # Find all .md files in design directory
    md_files = list(design_dir.glob("*.md"))

    if not md_files:
        sys.stderr.write(
            f"Error: No .md files found in {design_dir}\n"
        )
        sys.exit(1)

    # Get the file with the most recent modification time
    latest_file = max(md_files, key=lambda p: p.stat().st_mtime)

    # Strip all extensions from the filename
    stem = latest_file.name
    while Path(stem).suffix:
        stem = Path(stem).stem

    return stem


def resolve_languages(aliases: list[str]) -> list[str]:
    """Map user-supplied language names/aliases to canonical names.

    Returns a de-duplicated list preserving first-seen order.
    Exits with a clear error on any unrecognised alias.
    """
    canonical: list[str] = []
    seen: set[str] = set()
    for raw in aliases:
        key = raw.lower()
        if key not in ALIAS_MAP:
            valid = ", ".join(sorted(ALIAS_MAP.keys()))
            sys.stderr.write(
                f"Error: unrecognised language '{raw}'. "
                f"Valid names and aliases: {valid}\n"
            )
            sys.exit(1)
        name = ALIAS_MAP[key]
        if name not in seen:
            seen.add(name)
            canonical.append(name)
    return canonical


def create_zip(project_root: Path, zip_path: Path, rules: ExclusionRules) -> int:
    """Walk *project_root* recursively, apply exclusions, and write a zip archive.

    Files are stored with paths relative to *project_root*.
    *zip_path* is overwritten if it already exists.

    Returns the count of files written to the zip.
    """
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirs, files in os.walk(project_root):
            current_dir = Path(dirpath)
            # Prune excluded directories in-place so os.walk won't descend into them
            dirs[:] = [
                d for d in dirs
                if not should_exclude(current_dir / d, project_root, rules)
            ]
            for filename in files:
                file_path = current_dir / filename
                if should_exclude(file_path, project_root, rules):
                    continue
                arcname = str(file_path.relative_to(project_root))
                zf.write(file_path, arcname=arcname)
                file_count += 1
    return file_count


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
    parser.add_argument(
        "--language",
        nargs="+",
        metavar="LANG",
        default=None,
        help="Language(s) whose exclusion patterns to apply (default: all languages combined).",
    )

    # Add mutually exclusive group for --bundle and --unbundle
    mode_group = parser.add_mutually_exclusive_group(required=False)
    mode_group.add_argument(
        "--bundle",
        action="store_true",
        help="Bundle mode: create a zip file from the project.",
    )
    mode_group.add_argument(
        "--unbundle",
        action="store_true",
        help="Unbundle mode: extract a zip file.",
    )

    # Add --zip argument
    parser.add_argument(
        "--zip",
        metavar="ZIP_PATH",
        default=None,
        help="Path to the zip file to extract (required for --unbundle).",
    )

    args = parser.parse_args(argv)

    # Validate that one of --bundle or --unbundle is required
    if not args.bundle and not args.unbundle:
        parser.error("one of --bundle or --unbundle is required")

    return args


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path | None]:
    """Resolve and validate project_root based on mode; optionally resolve output_dir.

    In --bundle mode:
    - project_root defaults to the directory containing this script
    - output_dir defaults to the current working directory
    - Validates that project_root exists and is a directory
    - Creates output_dir if it doesn't exist
    - Returns (project_root, output_dir)

    In --unbundle mode:
    - project_root defaults to the directory containing this script
    - Validates that project_root exists and is a directory
    - Does not resolve or create output_dir
    - Returns (project_root, None)

    Exits with error message if project_root is invalid.
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

    # In bundle mode, resolve and create output_dir
    if args.bundle:
        if args.output is None:
            output_dir = Path.cwd()
        else:
            output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        return project_root, output_dir

    # In unbundle mode, don't resolve output_dir
    return project_root, None


def bundle_workspace(args: argparse.Namespace, project_root: Path, output_dir: Path) -> None:
    """Bundle the workspace into a zip file.

    Encapsulates the bundle logic: zip-name resolution, language resolution,
    exclusion rules, zip creation, and output summary.
    """
    canonical_langs = resolve_languages(args.language) if args.language is not None else None
    zip_name = resolve_zip_name(project_root)
    zip_path = output_dir / f"{zip_name}.zip"

    output_dir.mkdir(parents=True, exist_ok=True)
    rules = build_exclusion_rules(canonical_langs)
    count = create_zip(project_root, zip_path, rules)
    lang_label = ", ".join(canonical_langs) if canonical_langs is not None else "all"
    print(f"Created {zip_path}  [languages: {lang_label}]  ({count} files)")


def unbundle(args: argparse.Namespace, project_root: Path) -> None:
    """Extract a zip file into the workspace.

    Stub implementation; will be fully implemented in STORY-013.
    """
    raise NotImplementedError


def main(argv: list[str] | None = None) -> None:
    """Entry point."""
    args = parse_args(argv)
    project_root, output_dir = resolve_paths(args)
    if args.bundle:
        assert output_dir is not None  # In bundle mode, output_dir is always set
        bundle_workspace(args, project_root, output_dir)
    else:
        unbundle(args, project_root)


if __name__ == "__main__":
    main()
