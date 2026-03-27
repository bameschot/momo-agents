"""
test_e2e.py — End-to-end smoke tests for md_to_html.py (STORY-017)

Runnable standalone: `python test_e2e.py`
Exits 0 on success, non-zero with a printed failure message on failure.
No third-party test framework required.
"""

from __future__ import annotations

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
# Test: --help shows -i/--input and -o/--output
# ---------------------------------------------------------------------------

def test_help_output():
    """--help exits 0 and documents -i/--input and -o/--output."""
    result = subprocess.run(
        [PYTHON, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Expected exit code 0, got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "-i" in result.stdout or "--input" in result.stdout, (
        f"Expected '-i'/'--input' in help output, got: {result.stdout!r}"
    )
    assert "-o" in result.stdout or "--output" in result.stdout, (
        f"Expected '-o'/'--output' in help output, got: {result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Test: basic single-file end-to-end
# ---------------------------------------------------------------------------

def test_basic_e2e():
    """
    Creates one .md file, runs the script with -i/-o, and validates the output HTML.
    """
    tmpdir = Path(tempfile.mkdtemp())
    try:
        # Create a PNG image referenced by the markdown
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

        output_html = tmpdir / "output.html"
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "-i", str(md1), "-o", str(output_html)],
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

        # 5. Section slug present as id= attribute
        assert 'id="first"' in html, 'id="first" not found in output'

        # 6. At least one data:image URI present (image was referenced in md1)
        assert "data:image" in html, "No data:image URI found in output"

        # 7. Footnotes section present
        assert 'class="footnotes"' in html, 'footnotes section not found in output'

        # 8. toc-active CSS class definition present
        assert "toc-active" in html, ".toc-active CSS class not found in output"

        # 9. Success message on stdout
        assert "Written:" in result.stdout, (
            f"Expected 'Written:' in stdout, got: {result.stdout!r}"
        )

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test: default output path (no -o flag)
# ---------------------------------------------------------------------------

def test_default_output_path():
    """-i notes.md without -o produces notes.html in CWD."""
    tmpdir = Path(tempfile.mkdtemp())
    try:
        md = tmpdir / "notes.md"
        md.write_text("# Notes\n\nContent.\n", encoding="utf-8")

        result = subprocess.run(
            [PYTHON, str(SCRIPT), "-i", str(md)],
            capture_output=True,
            text=True,
            cwd=str(tmpdir),
        )
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}.\nstderr: {result.stderr}"
        )
        # Default output should be notes.html in CWD (tmpdir)
        default_output = tmpdir / "notes.html"
        assert default_output.exists(), (
            f"Expected default output {default_output} to exist"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test: no --input exits non-zero
# ---------------------------------------------------------------------------

def test_missing_input_arg():
    """Script must exit non-zero when --input is omitted."""
    result = subprocess.run(
        [PYTHON, str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "Expected non-zero exit when --input is omitted"


# ---------------------------------------------------------------------------
# Test: non-existent input file exits 1
# ---------------------------------------------------------------------------

def test_nonexistent_input_file():
    """Script must exit 1 when the --input file does not exist."""
    tmpdir = Path(tempfile.mkdtemp())
    try:
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "-i", str(tmpdir / "missing.md")],
            capture_output=True,
            text=True,
            cwd=str(tmpdir),
        )
        assert result.returncode == 1, (
            f"Expected exit code 1, got {result.returncode}"
        )
        assert result.stderr, "Expected error message on stderr"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test: non-.md extension exits 1
# ---------------------------------------------------------------------------

def test_non_md_extension():
    """Script must exit 1 when --input does not have .md extension."""
    tmpdir = Path(tempfile.mkdtemp())
    try:
        txt_file = tmpdir / "notes.txt"
        txt_file.write_text("# Hello\n\nContent.\n", encoding="utf-8")

        result = subprocess.run(
            [PYTHON, str(SCRIPT), "-i", str(txt_file)],
            capture_output=True,
            text=True,
            cwd=str(tmpdir),
        )
        assert result.returncode == 1, (
            f"Expected exit code 1 for non-.md input, got {result.returncode}"
        )
        assert result.stderr, "Expected error message on stderr about .md extension"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test: non-existent output directory exits 1
# ---------------------------------------------------------------------------

def test_nonexistent_output_dir():
    """Script must exit 1 when the output directory does not exist."""
    tmpdir = Path(tempfile.mkdtemp())
    try:
        md = tmpdir / "doc.md"
        md.write_text("# Hello\n\nContent.\n", encoding="utf-8")

        result = subprocess.run(
            [PYTHON, str(SCRIPT), "-i", str(md),
             "-o", str(tmpdir / "no_such_dir" / "out.html")],
            capture_output=True,
            text=True,
            cwd=str(tmpdir),
        )
        assert result.returncode == 1, (
            "Expected non-zero exit when output dir does not exist"
        )
        assert result.stderr, "Expected error message on stderr"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test: --order is unrecognised
# ---------------------------------------------------------------------------

def test_order_flag_unrecognised():
    """--order is no longer a valid argument and must produce a non-zero exit."""
    tmpdir = Path(tempfile.mkdtemp())
    try:
        md = tmpdir / "notes.md"
        md.write_text("# Notes\n\nContent.\n", encoding="utf-8")

        result = subprocess.run(
            [PYTHON, str(SCRIPT), "--order", str(md)],
            capture_output=True,
            text=True,
            cwd=str(tmpdir),
        )
        assert result.returncode != 0, (
            "Expected non-zero exit for unrecognised --order argument"
        )
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
            [PYTHON, str(SCRIPT), "-i", str(md), "-o", str(output_html)],
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
        ("--help shows -i/--input and -o/--output", test_help_output),
        ("Basic single-file end-to-end pipeline", test_basic_e2e),
        ("Default output path derived from input stem", test_default_output_path),
        ("Missing --input exits non-zero", test_missing_input_arg),
        ("Non-existent input file exits 1", test_nonexistent_input_file),
        ("Non-.md extension exits 1", test_non_md_extension),
        ("Non-existent output directory exits 1", test_nonexistent_output_dir),
        ("--order flag is unrecognised (removed)", test_order_flag_unrecognised),
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
