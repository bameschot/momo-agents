"""
Tests for STORY-009: Project Scaffold, Data Models & CLI

Covers parse_args() with valid/invalid inputs, default output path, title
override, --help, and missing/non-existent file handling.
"""
from __future__ import annotations

import pytest
from pathlib import Path

import sys
import os

# Make sure the workspace root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from md2pdf import Heading, ParseResult, parse_args


# ---------------------------------------------------------------------------
# Data Model Tests
# ---------------------------------------------------------------------------


def test_heading_dataclass():
    h = Heading(level=2, text="Hello World", slug="hello-world")
    assert h.level == 2
    assert h.text == "Hello World"
    assert h.slug == "hello-world"


def test_parse_result_dataclass():
    headings = [Heading(level=1, text="Title", slug="title")]
    pr = ParseResult(body_html="<p>body</p>", headings=headings, title="My Title")
    assert pr.body_html == "<p>body</p>"
    assert pr.headings == headings
    assert pr.title == "My Title"


def test_parse_result_title_optional():
    pr = ParseResult(body_html="", headings=[], title=None)
    assert pr.title is None


# ---------------------------------------------------------------------------
# parse_args() — valid input
# ---------------------------------------------------------------------------


def test_parse_args_valid_md_file(tmp_path):
    md_file = tmp_path / "sample.md"
    md_file.write_text("# Hello")
    args = parse_args([str(md_file)])
    assert args.input == md_file
    assert args.output == tmp_path / "sample.pdf"
    assert args.title is None


def test_parse_args_explicit_output(tmp_path):
    md_file = tmp_path / "doc.md"
    md_file.write_text("# Doc")
    out_file = tmp_path / "out.pdf"
    args = parse_args([str(md_file), "-o", str(out_file)])
    assert args.output == out_file


def test_parse_args_explicit_title(tmp_path):
    md_file = tmp_path / "doc.md"
    md_file.write_text("# Doc")
    args = parse_args([str(md_file), "-t", "My Custom Title"])
    assert args.title == "My Custom Title"


def test_parse_args_long_output_flag(tmp_path):
    md_file = tmp_path / "doc.md"
    md_file.write_text("# Doc")
    out_file = tmp_path / "result.pdf"
    args = parse_args([str(md_file), "--output", str(out_file)])
    assert args.output == out_file


def test_parse_args_long_title_flag(tmp_path):
    md_file = tmp_path / "doc.md"
    md_file.write_text("# Doc")
    args = parse_args([str(md_file), "--title", "Override"])
    assert args.title == "Override"


# ---------------------------------------------------------------------------
# Default output path: <same_dir>/<stem>.pdf
# ---------------------------------------------------------------------------


def test_parse_args_default_output_path_same_dir(tmp_path):
    md_file = tmp_path / "notes.md"
    md_file.write_text("# Notes")
    args = parse_args([str(md_file)])
    expected = md_file.parent / "notes.pdf"
    assert args.output == expected


def test_parse_args_default_output_path_nested(tmp_path):
    subdir = tmp_path / "sub"
    subdir.mkdir()
    md_file = subdir / "report.md"
    md_file.write_text("# Report")
    args = parse_args([str(md_file)])
    assert args.output == subdir / "report.pdf"


# ---------------------------------------------------------------------------
# parse_args() — error cases
# ---------------------------------------------------------------------------


def test_parse_args_missing_positional():
    """No positional argument → SystemExit."""
    with pytest.raises(SystemExit) as exc_info:
        parse_args([])
    assert exc_info.value.code != 0


def test_parse_args_nonexistent_file(tmp_path):
    """File that does not exist → SystemExit with non-zero code."""
    missing = tmp_path / "ghost.md"
    with pytest.raises(SystemExit) as exc_info:
        parse_args([str(missing)])
    assert exc_info.value.code != 0


def test_parse_args_wrong_extension(tmp_path):
    """File with wrong extension → SystemExit."""
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("hello")
    with pytest.raises(SystemExit) as exc_info:
        parse_args([str(txt_file)])
    assert exc_info.value.code != 0


def test_parse_args_directory_as_input(tmp_path):
    """Directory path as input → SystemExit."""
    with pytest.raises(SystemExit) as exc_info:
        parse_args([str(tmp_path)])
    assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# --help exits 0
# ---------------------------------------------------------------------------


def test_parse_args_help():
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--help"])
    assert exc_info.value.code == 0
