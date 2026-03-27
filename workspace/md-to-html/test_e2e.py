"""
test_e2e.py — End-to-end smoke tests for md_to_html.py (STORY-007)

Runnable standalone: `python test_e2e.py`
Exits 0 on success, non-zero with a printed failure message on failure.
No third-party test framework required.
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

# Locate the md_to_html.py script relative to this file
SCRIPT = Path(__file__).parent / "md_to_html.py"
PYTHON = sys.executable


def _make_minimal_png() -> bytes:
    """Return the bytes of a minimal 1×1 red PNG."""
    def chunk(name: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + name + data
        return c + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = chunk(b"IHDR", ihdr_data)
    raw_row = b"\x00\xFF\x00\x00"  # filter byte + R G B
    compressed = zlib.compress(raw_row)
    idat = chunk(b"IDAT", compressed)
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def run(description: str, func) -> bool:
    """Run *func* and return True on success, False on failure (prints message)."""
    try:
        func()
        print(f"  PASS  {description}")
        return True
    except AssertionError as exc:
        print(f"  FAIL  {description}")
        print(f"        {exc}")
        return False
    except Exception as exc:
        print(f"  ERROR {description}: {exc}")
        return False


# ---------------------------------------------------------------------------
# Core end-to-end test
# ---------------------------------------------------------------------------

def test_basic_e2e():
    """
    Creates two .md files (one with # heading, one without), runs the script,
    and validates the output HTML.
    """
    tmpdir = Path(tempfile.mkdtemp())
    try:
        # File 1: has a # heading and a local image and a footnote
        png_path = tmpdir / "image.png"
        png_path.write_bytes(_make_minimal_png())

        md1 = tmpdir / "first.md"
        md1.write_text(
            "# First Document\n\n"
            "Some text with a footnote.[^note]\n\n"
            "![Alt text](image.png)\n\n"
            "[^note]: This is the footnote definition.\n",
            encoding="utf-8",
        )

        # File 2: no # heading (only ## or no heading at all)
        md2 = tmpdir / "second.md"
        md2.write_text(
            "## Not a top-level heading\n\n"
            "Content without a top-level heading.\n",
            encoding="utf-8",
        )

        output_html = tmpdir / "output.html"
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "*.md", "-o", str(output_html)],
            capture_output=True,
            text=True,
            cwd=str(tmpdir),
        )

        # 1. Exit code 0
        assert result.returncode == 0, (
            f"Expected exit code 0, got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        # 2. Read output and validate UTF-8
        html_bytes = output_html.read_bytes()
        html = html_bytes.decode("utf-8")  # raises UnicodeDecodeError if not valid

        # 3. DOCTYPE present
        assert "<!DOCTYPE html>" in html, "<!DOCTYPE html> not found in output"

        # 4. TOC nav present
        assert '<nav id="toc">' in html, '<nav id="toc"> not found in output'

        # 5. Both section slugs present as id= attributes
        assert 'id="first"' in html, 'id="first" not found in output'
        assert 'id="second"' in html, 'id="second" not found in output'

        # 6. At least one data:image URI present (image was referenced in md1)
        assert "data:image" in html, "No data:image URI found in output"

        # 7. Footnotes section present (footnote was used in md1)
        assert 'class="footnotes"' in html, 'footnotes section not found in output'

        # 8. toc-active CSS class definition present
        assert "toc-active" in html, ".toc-active CSS class not found in output"

        # 9. Warning about missing top-level heading on stderr
        assert "Warning:" in result.stderr and "second.md" in result.stderr, (
            f"Expected warning about 'second.md' on stderr, got: {result.stderr!r}"
        )

        # 10. Success message on stdout
        assert "Written:" in result.stdout, (
            f"Expected 'Written:' in stdout, got: {result.stdout!r}"
        )

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test: non-existent output directory exits non-zero
# ---------------------------------------------------------------------------

def test_nonexistent_output_dir():
    """Script must exit non-zero when the output directory does not exist."""
    tmpdir = Path(tempfile.mkdtemp())
    try:
        md = tmpdir / "doc.md"
        md.write_text("# Hello\n\nContent.\n", encoding="utf-8")

        result = subprocess.run(
            [PYTHON, str(SCRIPT), "*.md", "-o", str(tmpdir / "no_such_dir" / "out.html")],
            capture_output=True,
            text=True,
            cwd=str(tmpdir),
        )
        assert result.returncode != 0, (
            "Expected non-zero exit when output dir does not exist"
        )
        assert result.stderr, "Expected error message on stderr"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test: --order flag
# ---------------------------------------------------------------------------

def test_order_flag():
    """Sections appear in the --order-specified sequence in the output HTML."""
    tmpdir = Path(tempfile.mkdtemp())
    try:
        alpha = tmpdir / "alpha.md"
        alpha.write_text("# Alpha\n\nAlpha content.\n", encoding="utf-8")
        beta = tmpdir / "beta.md"
        beta.write_text("# Beta\n\nBeta content.\n", encoding="utf-8")

        output_html = tmpdir / "output.html"
        # Request beta first, then alpha
        result = subprocess.run(
            [
                PYTHON, str(SCRIPT), "*.md",
                "--order", str(beta), str(alpha),
                "-o", str(output_html),
            ],
            capture_output=True,
            text=True,
            cwd=str(tmpdir),
        )
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}.\nstderr: {result.stderr}"
        )
        html = output_html.read_text(encoding="utf-8")
        pos_beta = html.index('id="beta"')
        pos_alpha = html.index('id="alpha"')
        assert pos_beta < pos_alpha, (
            "Expected 'beta' section before 'alpha' section in output"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test: recursive glob
# ---------------------------------------------------------------------------

def test_recursive_glob():
    """Script handles recursive glob patterns covering subdirectories."""
    tmpdir = Path(tempfile.mkdtemp())
    try:
        sub = tmpdir / "sub"
        sub.mkdir()

        root_md = tmpdir / "root.md"
        root_md.write_text("# Root\n\nRoot content.\n", encoding="utf-8")
        sub_md = sub / "child.md"
        sub_md.write_text("# Child\n\nChild content.\n", encoding="utf-8")

        output_html = tmpdir / "output.html"
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "**/*.md", "-o", str(output_html)],
            capture_output=True,
            text=True,
            cwd=str(tmpdir),
        )
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}.\nstderr: {result.stderr}"
        )
        html = output_html.read_text(encoding="utf-8")
        assert 'id="root"' in html, 'id="root" not found in recursive glob output'
        assert 'id="child"' in html, 'id="child" not found in recursive glob output'
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test: IntersectionObserver scroll-spy JS is present and safe
# ---------------------------------------------------------------------------

def test_scrollspy_js():
    """Output HTML contains IntersectionObserver scroll-spy script (no eval/document.write)."""
    tmpdir = Path(tempfile.mkdtemp())
    try:
        md = tmpdir / "doc.md"
        md.write_text("# Hello\n\nContent.\n", encoding="utf-8")

        output_html = tmpdir / "output.html"
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "*.md", "-o", str(output_html)],
            capture_output=True,
            text=True,
            cwd=str(tmpdir),
        )
        assert result.returncode == 0

        html = output_html.read_text(encoding="utf-8")
        assert "IntersectionObserver" in html, "IntersectionObserver not found in script"
        assert "toc-active" in html, "toc-active not found in script"
        assert "eval(" not in html, "eval() must not be present in output"
        assert "document.write" not in html, "document.write must not be present in output"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    tests = [
        ("Basic end-to-end pipeline", test_basic_e2e),
        ("Non-existent output directory exits non-zero", test_nonexistent_output_dir),
        ("--order flag controls section order", test_order_flag),
        ("Recursive glob covers subdirectories", test_recursive_glob),
        ("Scroll-spy JS is present and safe", test_scrollspy_js),
    ]

    print(f"Running {len(tests)} end-to-end tests against {SCRIPT}...")
    passed = 0
    failed = 0
    for description, func in tests:
        if run(description, func):
            passed += 1
        else:
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
