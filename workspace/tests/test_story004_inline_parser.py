"""
Tests for STORY-004: Inline-Level Markdown Parser

Tests cover:
  - HTML auto-escape of & < > in non-code spans
  - Inline code (`code`) — content frozen, bold/etc not applied inside
  - Bold (**text** and __text__)
  - Italic (*text* and _text_) — no conflict with bold
  - Strikethrough (~~text~~)
  - Links ([label](url)) — recursive label parsing
  - Images (![alt](src)) — embed_image is called
  - Processing order (code first, images before links, bold before italic)
  - Integration: full convert() output with inline markup
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from md2html import convert, inline_parse  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def base_dir(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# HTML auto-escape
# ---------------------------------------------------------------------------


class TestHtmlAutoEscape:
    def test_ampersand_escaped(self, base_dir: Path) -> None:
        result = inline_parse("cats & dogs", base_dir)
        assert "&amp;" in result
        assert " & " not in result

    def test_less_than_escaped(self, base_dir: Path) -> None:
        result = inline_parse("a < b", base_dir)
        assert "&lt;" in result
        assert " < " not in result

    def test_greater_than_escaped(self, base_dir: Path) -> None:
        result = inline_parse("a > b", base_dir)
        assert "&gt;" in result
        assert " > " not in result

    def test_all_three_escaped(self, base_dir: Path) -> None:
        result = inline_parse("x & y < z > w", base_dir)
        assert "&amp;" in result
        assert "&lt;" in result
        assert "&gt;" in result

    def test_plain_text_unchanged(self, base_dir: Path) -> None:
        result = inline_parse("hello world", base_dir)
        assert result == "hello world"


# ---------------------------------------------------------------------------
# Inline code
# ---------------------------------------------------------------------------


class TestInlineCode:
    def test_single_backtick(self, base_dir: Path) -> None:
        result = inline_parse("`code`", base_dir)
        assert "<code>code</code>" in result

    def test_code_content_html_escaped(self, base_dir: Path) -> None:
        result = inline_parse("`a < b`", base_dir)
        assert "<code>a &lt; b</code>" in result

    def test_bold_not_applied_inside_code(self, base_dir: Path) -> None:
        result = inline_parse("`**bold syntax**`", base_dir)
        assert "<strong>" not in result
        assert "**bold syntax**" in result

    def test_italic_not_applied_inside_code(self, base_dir: Path) -> None:
        result = inline_parse("`*italic*`", base_dir)
        assert "<em>" not in result

    def test_link_not_applied_inside_code(self, base_dir: Path) -> None:
        result = inline_parse("`[link](url)`", base_dir)
        assert "<a " not in result

    def test_code_amid_text(self, base_dir: Path) -> None:
        result = inline_parse("use `foo()` here", base_dir)
        assert "<code>foo()</code>" in result
        assert "use" in result
        assert "here" in result


# ---------------------------------------------------------------------------
# Bold
# ---------------------------------------------------------------------------


class TestBold:
    def test_double_asterisk(self, base_dir: Path) -> None:
        result = inline_parse("**bold**", base_dir)
        assert "<strong>bold</strong>" in result

    def test_double_underscore(self, base_dir: Path) -> None:
        result = inline_parse("__bold__", base_dir)
        assert "<strong>bold</strong>" in result

    def test_bold_amid_text(self, base_dir: Path) -> None:
        result = inline_parse("This is **important** text.", base_dir)
        assert "<strong>important</strong>" in result
        assert "This is" in result
        assert "text." in result


# ---------------------------------------------------------------------------
# Italic
# ---------------------------------------------------------------------------


class TestItalic:
    def test_single_asterisk(self, base_dir: Path) -> None:
        result = inline_parse("*italic*", base_dir)
        assert "<em>italic</em>" in result

    def test_single_underscore(self, base_dir: Path) -> None:
        result = inline_parse("_italic_", base_dir)
        assert "<em>italic</em>" in result

    def test_bold_not_confused_with_italic(self, base_dir: Path) -> None:
        result = inline_parse("**bold**", base_dir)
        assert "<strong>bold</strong>" in result
        # Should not produce <em> wrapping <strong>
        assert result.count("<em>") == 0

    def test_bold_and_italic_in_same_sentence(self, base_dir: Path) -> None:
        result = inline_parse("**bold** and *italic*", base_dir)
        assert "<strong>bold</strong>" in result
        assert "<em>italic</em>" in result


# ---------------------------------------------------------------------------
# Strikethrough
# ---------------------------------------------------------------------------


class TestStrikethrough:
    def test_double_tilde(self, base_dir: Path) -> None:
        result = inline_parse("~~strikethrough~~", base_dir)
        assert "<del>strikethrough</del>" in result

    def test_strikethrough_amid_text(self, base_dir: Path) -> None:
        result = inline_parse("This is ~~old~~ text.", base_dir)
        assert "<del>old</del>" in result


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


class TestLinks:
    def test_simple_link(self, base_dir: Path) -> None:
        result = inline_parse("[Visit](https://example.com)", base_dir)
        assert '<a href="https://example.com">Visit</a>' in result

    def test_link_label_italic_recursive(self, base_dir: Path) -> None:
        result = inline_parse("[*italic label*](https://example.com)", base_dir)
        assert "<a href" in result
        assert "<em>italic label</em>" in result

    def test_link_label_bold_recursive(self, base_dir: Path) -> None:
        result = inline_parse("[**bold**](https://example.com)", base_dir)
        assert "<strong>bold</strong>" in result

    def test_link_amid_text(self, base_dir: Path) -> None:
        result = inline_parse("Click [here](http://example.com) to visit.", base_dir)
        assert '<a href="http://example.com">here</a>' in result
        assert "Click" in result
        assert "to visit." in result


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


class TestImages:
    def test_http_image_unchanged(self, base_dir: Path) -> None:
        result = inline_parse("![alt](https://example.com/img.png)", base_dir)
        assert '<img src="https://example.com/img.png"' in result
        assert 'alt="alt"' in result

    def test_local_image_embedded(self, base_dir: Path, tmp_path: Path) -> None:
        # Create a real PNG fixture (minimal 1-byte PNG is not valid, so use a real one)
        img_path = tmp_path / "test.png"
        # Write a minimal valid bytes (not a real PNG but enough for base64 encoding test)
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG magic bytes
        result = inline_parse(f"![my image]({img_path.name})", tmp_path)
        assert "data:image/png;base64," in result
        assert 'alt="my image"' in result

    def test_missing_image_src_returned(self, base_dir: Path) -> None:
        result = inline_parse("![alt](nonexistent.png)", base_dir)
        # embed_image prints warning and returns original src
        assert 'src="nonexistent.png"' in result

    def test_image_before_link_no_conflict(self, base_dir: Path) -> None:
        # Image uses ![ which should not be consumed by link pattern
        result = inline_parse("![img](img.jpg) and [link](url)", base_dir)
        assert "<img " in result
        assert "<a href" in result

    def test_embed_image_called(self, base_dir: Path) -> None:
        with patch("md2html.embed_image", return_value="data:image/png;base64,TEST") as mock:
            result = inline_parse("![alt](img.png)", base_dir)
            mock.assert_called_once_with("img.png", base_dir)
            assert "data:image/png;base64,TEST" in result


# ---------------------------------------------------------------------------
# Integration: convert() now applies inline_parse
# ---------------------------------------------------------------------------


class TestInlineIntegration:
    def test_paragraph_with_bold(self, base_dir: Path) -> None:
        result = convert("This is **important**.\n", base_dir)
        assert "<strong>important</strong>" in result.body_html

    def test_paragraph_with_escaped_html(self, base_dir: Path) -> None:
        result = convert("Use a < b && c > d.\n", base_dir)
        assert "&lt;" in result.body_html
        assert "&gt;" in result.body_html
        assert "&amp;" in result.body_html

    def test_heading_plain_text_in_heading_object(self, base_dir: Path) -> None:
        result = convert("# **Bold** Title\n", base_dir)
        # The heading object text should be plain (no HTML tags) for slug generation
        assert result.headings[0].text == "**Bold** Title"

    def test_heading_html_rendered_in_body(self, base_dir: Path) -> None:
        result = convert("# **Bold** Title\n", base_dir)
        # The body_html should have the inline parsed version
        assert "<strong>Bold</strong>" in result.body_html

    def test_blockquote_inline(self, base_dir: Path) -> None:
        result = convert("> This *is* quoted.\n", base_dir)
        assert "<em>is</em>" in result.body_html

    def test_inline_code_in_paragraph(self, base_dir: Path) -> None:
        result = convert("Use the `convert()` function.\n", base_dir)
        assert "<code>convert()</code>" in result.body_html

    def test_link_in_paragraph(self, base_dir: Path) -> None:
        result = convert("See [docs](https://example.com).\n", base_dir)
        assert '<a href="https://example.com">docs</a>' in result.body_html

    def test_mixed_inline_content(self, base_dir: Path) -> None:
        md = "**Bold**, *italic*, ~~strike~~, and `code` in one line.\n"
        result = convert(md, base_dir)
        body = result.body_html
        assert "<strong>Bold</strong>" in body
        assert "<em>italic</em>" in body
        assert "<del>strike</del>" in body
        assert "<code>code</code>" in body

    def test_code_block_not_inline_parsed(self, base_dir: Path) -> None:
        md = "```\n**not bold**\n```\n"
        result = convert(md, base_dir)
        assert "**not bold**" in result.body_html
        assert "<strong>" not in result.body_html
