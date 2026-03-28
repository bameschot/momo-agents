"""
Tests for STORY-012: MarkdownParser — Inline-Level Parsing & ImageEmbedder

Tests cover:
  - embed_image(): HTTP/HTTPS passthrough, local PNG/JPG/SVG embedding,
    missing file warning, unsupported extension warning
  - inline_parse(): bold, italic, strikethrough, inline code, links, images
  - convert(): full pipeline returns ParseResult with inline-formatted body_html
  - Code blocks are NOT inline-parsed (bold/italic remain literal inside <pre>)
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from md2pdf import convert, embed_image, inline_parse  # noqa: E402

BASE_DIR = Path(".")

# ---------------------------------------------------------------------------
# Minimal image bytes
# ---------------------------------------------------------------------------

_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)
_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
_SVG_BYTES = b'<svg xmlns="http://www.w3.org/2000/svg"/>'


# ---------------------------------------------------------------------------
# embed_image tests
# ---------------------------------------------------------------------------


class TestEmbedImage:
    def test_http_url_unchanged(self, tmp_path: Path) -> None:
        url = "http://example.com/img.png"
        assert embed_image(url, tmp_path) == url

    def test_https_url_unchanged(self, tmp_path: Path) -> None:
        url = "https://example.com/img.png"
        assert embed_image(url, tmp_path) == url

    def test_local_png_returns_data_uri(self, tmp_path: Path) -> None:
        (tmp_path / "image.png").write_bytes(_PNG_BYTES)
        result = embed_image("image.png", tmp_path)
        assert result.startswith("data:image/png;base64,")
        expected_b64 = base64.b64encode(_PNG_BYTES).decode("ascii")
        assert result == f"data:image/png;base64,{expected_b64}"

    def test_local_jpg_returns_data_uri(self, tmp_path: Path) -> None:
        (tmp_path / "photo.jpg").write_bytes(_JPEG_BYTES)
        result = embed_image("photo.jpg", tmp_path)
        assert result.startswith("data:image/jpeg;base64,")

    def test_local_jpeg_extension(self, tmp_path: Path) -> None:
        (tmp_path / "photo.jpeg").write_bytes(_JPEG_BYTES)
        result = embed_image("photo.jpeg", tmp_path)
        assert result.startswith("data:image/jpeg;base64,")

    def test_local_svg_returns_data_uri(self, tmp_path: Path) -> None:
        (tmp_path / "icon.svg").write_bytes(_SVG_BYTES)
        result = embed_image("icon.svg", tmp_path)
        assert result.startswith("data:image/svg+xml;base64,")

    def test_missing_file_returns_original_src(self, tmp_path: Path) -> None:
        result = embed_image("nonexistent.png", tmp_path)
        assert result == "nonexistent.png"

    def test_missing_file_prints_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        embed_image("nonexistent.png", tmp_path)
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "nonexistent.png" in captured.err

    def test_missing_file_does_not_raise(self, tmp_path: Path) -> None:
        # Must not raise any exception.
        embed_image("no_such.png", tmp_path)

    def test_case_insensitive_extension(self, tmp_path: Path) -> None:
        (tmp_path / "photo.PNG").write_bytes(_PNG_BYTES)
        result = embed_image("photo.PNG", tmp_path)
        assert result.startswith("data:image/png;base64,")


# ---------------------------------------------------------------------------
# inline_parse tests
# ---------------------------------------------------------------------------


class TestInlineParse:
    def test_bold_double_asterisk(self, tmp_path: Path) -> None:
        result = inline_parse("**bold**", tmp_path)
        assert "<strong>bold</strong>" in result

    def test_bold_double_underscore(self, tmp_path: Path) -> None:
        result = inline_parse("__bold__", tmp_path)
        assert "<strong>bold</strong>" in result

    def test_italic_single_asterisk(self, tmp_path: Path) -> None:
        result = inline_parse("*italic*", tmp_path)
        assert "<em>italic</em>" in result

    def test_italic_single_underscore(self, tmp_path: Path) -> None:
        result = inline_parse("_italic_", tmp_path)
        assert "<em>italic</em>" in result

    def test_strikethrough(self, tmp_path: Path) -> None:
        result = inline_parse("~~strike~~", tmp_path)
        assert "<del>strike</del>" in result

    def test_inline_code(self, tmp_path: Path) -> None:
        result = inline_parse("`code`", tmp_path)
        assert "<code>code</code>" in result

    def test_inline_code_html_escaped(self, tmp_path: Path) -> None:
        result = inline_parse("`a < b`", tmp_path)
        assert "<code>a &lt; b</code>" in result

    def test_link(self, tmp_path: Path) -> None:
        result = inline_parse("[label](http://example.com)", tmp_path)
        assert '<a href="http://example.com">label</a>' in result

    def test_image_http(self, tmp_path: Path) -> None:
        result = inline_parse("![alt](https://example.com/img.png)", tmp_path)
        assert 'alt="alt"' in result
        assert 'src="https://example.com/img.png"' in result

    def test_image_local_png(self, tmp_path: Path) -> None:
        (tmp_path / "img.png").write_bytes(_PNG_BYTES)
        result = inline_parse("![my image](img.png)", tmp_path)
        assert "data:image/png;base64," in result
        assert 'alt="my image"' in result

    def test_html_ampersand_escaped(self, tmp_path: Path) -> None:
        result = inline_parse("cats & dogs", tmp_path)
        assert "&amp;" in result
        assert " & " not in result

    def test_html_less_than_escaped(self, tmp_path: Path) -> None:
        result = inline_parse("a < b", tmp_path)
        assert "&lt;" in result

    def test_html_greater_than_escaped(self, tmp_path: Path) -> None:
        result = inline_parse("a > b", tmp_path)
        assert "&gt;" in result

    def test_bold_not_applied_inside_code(self, tmp_path: Path) -> None:
        result = inline_parse("`**bold syntax**`", tmp_path)
        assert "<strong>" not in result
        assert "**bold syntax**" in result

    def test_bold_not_confused_with_italic(self, tmp_path: Path) -> None:
        result = inline_parse("**bold**", tmp_path)
        assert "<strong>bold</strong>" in result
        assert result.count("<em>") == 0


# ---------------------------------------------------------------------------
# convert() integration tests — inline parsing in full pipeline
# ---------------------------------------------------------------------------


class TestConvertInline:
    def test_bold_in_paragraph(self) -> None:
        result = convert("**bold**", BASE_DIR)
        assert "<strong>bold</strong>" in result.body_html

    def test_italic_in_paragraph(self) -> None:
        result = convert("*italic*", BASE_DIR)
        assert "<em>italic</em>" in result.body_html

    def test_strikethrough_in_paragraph(self) -> None:
        result = convert("~~strike~~", BASE_DIR)
        assert "<del>strike</del>" in result.body_html

    def test_inline_code_in_paragraph(self) -> None:
        result = convert("`code`", BASE_DIR)
        assert "<code>code</code>" in result.body_html

    def test_link_in_paragraph(self) -> None:
        result = convert("[label](http://example.com)", BASE_DIR)
        assert '<a href="http://example.com">label</a>' in result.body_html

    def test_image_local_png(self, tmp_path: Path) -> None:
        (tmp_path / "img.png").write_bytes(_PNG_BYTES)
        result = convert("![alt](img.png)", tmp_path)
        assert "data:image/png;base64," in result.body_html

    def test_code_block_not_inline_parsed(self) -> None:
        md = "```\n**not bold**\n```"
        result = convert(md, BASE_DIR)
        assert "**not bold**" in result.body_html
        assert "<strong>" not in result.body_html

    def test_returns_parse_result(self) -> None:
        from md2pdf import ParseResult
        result = convert("**bold**", BASE_DIR)
        assert isinstance(result, ParseResult)
        assert isinstance(result.body_html, str)
