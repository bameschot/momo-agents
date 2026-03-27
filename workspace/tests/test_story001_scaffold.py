"""
Tests for STORY-001: Project Scaffold, Dataclasses & CLI

Tests cover parse_args() behaviour:
  - valid .md path input
  - explicit -o output path
  - explicit -t title
  - --help flag (SystemExit with code 0)
  - missing positional argument (SystemExit non-zero)
  - default output path derivation

No filesystem writes occur during these tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure workspace root is on the import path regardless of how pytest is invoked.
sys.path.insert(0, str(Path(__file__).parent.parent))

import md2html  # noqa: E402  (import after path manipulation)
from md2html import Heading, ParseResult, parse_args  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_md(tmp_path: Path) -> Path:
    """Create a temporary .md file for use in parse_args() tests."""
    md_file = tmp_path / "sample.md"
    md_file.write_text("# Hello\n\nWorld.\n", encoding="utf-8")
    return md_file


# ---------------------------------------------------------------------------
# Dataclass smoke tests
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_heading_fields(self) -> None:
        h = Heading(level=1, text="Introduction", slug="introduction")
        assert h.level == 1
        assert h.text == "Introduction"
        assert h.slug == "introduction"

    def test_parse_result_fields(self) -> None:
        h = Heading(level=2, text="Sub", slug="sub")
        pr = ParseResult(body_html="<p>Hi</p>", headings=[h], title="Doc")
        assert pr.body_html == "<p>Hi</p>"
        assert pr.headings == [h]
        assert pr.title == "Doc"

    def test_parse_result_title_none(self) -> None:
        pr = ParseResult(body_html="", headings=[], title=None)
        assert pr.title is None

    def test_heading_type_annotations(self) -> None:
        """Verify the expected field names exist on the dataclass."""
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(Heading)}
        assert field_names == {"level", "text", "slug"}

    def test_parse_result_type_annotations(self) -> None:
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(ParseResult)}
        assert field_names == {"body_html", "headings", "title"}


# ---------------------------------------------------------------------------
# parse_args() tests
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_valid_md_path(self, tmp_md: Path) -> None:
        """A valid .md file path should be accepted."""
        args = parse_args([str(tmp_md)])
        assert args.input == tmp_md

    def test_default_output_path(self, tmp_md: Path) -> None:
        """When -o is omitted, output defaults to <stem>.html in the same dir."""
        args = parse_args([str(tmp_md)])
        expected = tmp_md.parent / (tmp_md.stem + ".html")
        assert args.output == expected

    def test_explicit_output_path(self, tmp_md: Path, tmp_path: Path) -> None:
        """An explicit -o path should be respected."""
        out = tmp_path / "out" / "result.html"
        args = parse_args([str(tmp_md), "-o", str(out)])
        assert args.output == out

    def test_long_output_flag(self, tmp_md: Path, tmp_path: Path) -> None:
        """--output long form should work identically to -o."""
        out = tmp_path / "dest.html"
        args = parse_args([str(tmp_md), "--output", str(out)])
        assert args.output == out

    def test_explicit_title(self, tmp_md: Path) -> None:
        """An explicit -t title should be stored on the namespace."""
        args = parse_args([str(tmp_md), "-t", "My Custom Title"])
        assert args.title == "My Custom Title"

    def test_long_title_flag(self, tmp_md: Path) -> None:
        """--title long form should work identically to -t."""
        args = parse_args([str(tmp_md), "--title", "Another Title"])
        assert args.title == "Another Title"

    def test_title_defaults_to_none(self, tmp_md: Path) -> None:
        """When -t is omitted, title should be None."""
        args = parse_args([str(tmp_md)])
        assert args.title is None

    def test_help_flag_exits_zero(self) -> None:
        """--help should raise SystemExit with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_missing_positional_exits_nonzero(self) -> None:
        """Omitting the positional input arg should raise SystemExit with non-zero code."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args([])
        assert exc_info.value.code != 0

    def test_nonexistent_file_exits_nonzero(self, tmp_path: Path) -> None:
        """A path to a non-existent file should raise SystemExit with non-zero code."""
        nonexistent = tmp_path / "does_not_exist.md"
        with pytest.raises(SystemExit) as exc_info:
            parse_args([str(nonexistent)])
        assert exc_info.value.code != 0

    def test_no_filesystem_writes(self, tmp_md: Path, tmp_path: Path) -> None:
        """Calling parse_args() must not create any files."""
        files_before = set(tmp_path.rglob("*"))
        parse_args([str(tmp_md)])
        files_after = set(tmp_path.rglob("*"))
        # Only the .md file itself should exist; nothing new written.
        assert files_after == files_before

    def test_output_path_is_path_object(self, tmp_md: Path) -> None:
        """The output attribute should be a pathlib.Path instance."""
        args = parse_args([str(tmp_md)])
        assert isinstance(args.output, Path)

    def test_input_path_is_path_object(self, tmp_md: Path) -> None:
        """The input attribute should be a pathlib.Path instance."""
        args = parse_args([str(tmp_md)])
        assert isinstance(args.input, Path)


# ---------------------------------------------------------------------------
# Module-level constant smoke tests
# ---------------------------------------------------------------------------


class TestModuleConstants:
    def test_css_constant_exists(self) -> None:
        assert hasattr(md2html, "CSS")
        assert isinstance(md2html.CSS, str)

    def test_js_constant_exists(self) -> None:
        assert hasattr(md2html, "JS")
        assert isinstance(md2html.JS, str)


# ---------------------------------------------------------------------------
# Stub function smoke tests
# ---------------------------------------------------------------------------


class TestStubFunctions:
    def test_convert_returns_parse_result(self, tmp_path: Path) -> None:
        result = md2html.convert("# Hello\n", tmp_path)
        assert isinstance(result, ParseResult)

    def test_build_toc_returns_str(self) -> None:
        toc = md2html.build_toc([])
        assert isinstance(toc, str)

    def test_render_page_returns_str(self, tmp_path: Path) -> None:
        pr = ParseResult(body_html="", headings=[], title=None)
        html = md2html.render_page(pr, "Title", "")
        assert isinstance(html, str)

    def test_embed_image_returns_str(self, tmp_path: Path) -> None:
        src = md2html.embed_image("https://example.com/img.png", tmp_path)
        assert isinstance(src, str)
