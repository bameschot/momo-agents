"""
test_parser.py — Unit tests for MarkdownParser block elements (STORY-002)
and inline elements (STORY-003).
"""

from __future__ import annotations

import sys
import os

# Allow running from any directory
sys.path.insert(0, os.path.dirname(__file__))

import base64
import struct
import zlib
import tempfile
from pathlib import Path

from md_to_html import MarkdownParser, slugify, Heading, embed_image, _process_inline


def assert_equal(actual: str, expected: str, msg: str = "") -> None:
    actual_s = actual.strip()
    expected_s = expected.strip()
    assert actual_s == expected_s, (
        f"{msg}\nExpected:\n{expected_s!r}\nActual:\n{actual_s!r}"
    )


def assert_in(needle: str, haystack: str, msg: str = "") -> None:
    assert needle in haystack, f"{msg}\n{needle!r} not found in:\n{haystack!r}"


# ---------------------------------------------------------------------------
# slugify helper
# ---------------------------------------------------------------------------

def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"

def test_slugify_special_chars():
    assert slugify("Hello, World!") == "hello-world"

def test_slugify_consecutive_hyphens():
    assert slugify("Hello  World") == "hello-world"

def test_slugify_leading_trailing():
    assert slugify("  Hello  ") == "hello"


# ---------------------------------------------------------------------------
# ATX Headings
# ---------------------------------------------------------------------------

def test_h1():
    p = MarkdownParser()
    html = p.parse("# Hello World")
    assert_equal(html, '<h1 id="hello-world">Hello World</h1>', "h1")

def test_h2():
    p = MarkdownParser()
    html = p.parse("## Section Two")
    assert_equal(html, '<h2 id="section-two">Section Two</h2>', "h2")

def test_h6():
    p = MarkdownParser()
    html = p.parse("###### Deep")
    assert_equal(html, '<h6 id="deep">Deep</h6>', "h6")

def test_heading_populates_headings():
    p = MarkdownParser()
    p.parse("# Title\n\n## Sub")
    assert len(p.headings) == 2
    assert p.headings[0] == Heading(level=1, text="Title", anchor="title")
    assert p.headings[1] == Heading(level=2, text="Sub", anchor="sub")

def test_heading_anchor_special_chars():
    p = MarkdownParser()
    html = p.parse("# Hello, World!")
    assert 'id="hello-world"' in html


# ---------------------------------------------------------------------------
# Paragraphs
# ---------------------------------------------------------------------------

def test_paragraph_basic():
    p = MarkdownParser()
    html = p.parse("Hello world")
    assert_equal(html, "<p>Hello world</p>", "paragraph")

def test_paragraph_multiline():
    p = MarkdownParser()
    html = p.parse("Line one\nLine two")
    assert "<p>" in html
    assert "Line one" in html
    assert "Line two" in html


# ---------------------------------------------------------------------------
# Fenced Code Blocks
# ---------------------------------------------------------------------------

def test_fenced_code_backtick():
    p = MarkdownParser()
    md = "```python\nprint('hello')\n```"
    html = p.parse(md)
    assert '<pre><code class="language-python">' in html
    assert "print('hello')" in html

def test_fenced_code_tilde():
    p = MarkdownParser()
    md = "~~~\nsome code\n~~~"
    html = p.parse(md)
    assert "<pre><code>" in html
    assert "some code" in html

def test_fenced_code_no_lang():
    p = MarkdownParser()
    md = "```\ncode here\n```"
    html = p.parse(md)
    assert "<pre><code>" in html

def test_fenced_code_html_escape():
    p = MarkdownParser()
    md = "```\n<tag> & \"quote\"\n```"
    html = p.parse(md)
    assert "&lt;tag&gt;" in html
    assert "&amp;" in html
    assert "&quot;" in html
    assert "<tag>" not in html


# ---------------------------------------------------------------------------
# Blockquotes
# ---------------------------------------------------------------------------

def test_blockquote_simple():
    p = MarkdownParser()
    html = p.parse("> Hello from blockquote")
    assert "<blockquote>" in html
    assert "Hello from blockquote" in html

def test_blockquote_nested():
    p = MarkdownParser()
    md = "> outer\n>> inner"
    html = p.parse(md)
    # Should have two blockquote levels
    assert html.count("<blockquote>") >= 2
    assert "inner" in html

def test_blockquote_consecutive():
    p = MarkdownParser()
    md = "> line one\n> line two"
    html = p.parse(md)
    assert html.count("<blockquote>") == 1
    assert "line one" in html
    assert "line two" in html


# ---------------------------------------------------------------------------
# Horizontal Rules
# ---------------------------------------------------------------------------

def test_hr_dashes():
    p = MarkdownParser()
    html = p.parse("---")
    assert_equal(html, "<hr>", "hr dashes")

def test_hr_stars():
    p = MarkdownParser()
    html = p.parse("***")
    assert_equal(html, "<hr>", "hr stars")

def test_hr_underscores():
    p = MarkdownParser()
    html = p.parse("___")
    assert_equal(html, "<hr>", "hr underscores")

def test_hr_with_spaces():
    p = MarkdownParser()
    html = p.parse("- - -")
    assert_equal(html, "<hr>", "hr with spaces")


# ---------------------------------------------------------------------------
# Unordered Lists
# ---------------------------------------------------------------------------

def test_ul_basic():
    p = MarkdownParser()
    md = "- item one\n- item two\n- item three"
    html = p.parse(md)
    assert "<ul>" in html
    assert "<li>item one</li>" in html
    assert "<li>item two</li>" in html

def test_ul_nested():
    p = MarkdownParser()
    md = "- parent\n  - child\n  - child2"
    html = p.parse(md)
    assert "<ul>" in html
    assert "parent" in html
    assert "child" in html
    # Nested ul inside li
    assert html.count("<ul>") >= 2

def test_ul_plus_bullet():
    p = MarkdownParser()
    md = "+ item"
    html = p.parse(md)
    assert "<ul>" in html
    assert "<li>item</li>" in html

def test_ul_star_bullet():
    p = MarkdownParser()
    md = "* item"
    html = p.parse(md)
    assert "<ul>" in html


# ---------------------------------------------------------------------------
# Ordered Lists
# ---------------------------------------------------------------------------

def test_ol_basic():
    p = MarkdownParser()
    md = "1. first\n2. second\n3. third"
    html = p.parse(md)
    assert "<ol>" in html
    assert "<li>first</li>" in html
    assert "<li>second</li>" in html

def test_ol_nested():
    p = MarkdownParser()
    md = "1. parent\n   1. child"
    html = p.parse(md)
    assert "<ol>" in html
    assert "parent" in html
    assert "child" in html


# ---------------------------------------------------------------------------
# Task Lists
# ---------------------------------------------------------------------------

def test_task_list_unchecked():
    p = MarkdownParser()
    md = "- [ ] do this"
    html = p.parse(md)
    assert '<input type="checkbox" disabled>' in html
    assert "do this" in html

def test_task_list_checked():
    p = MarkdownParser()
    md = "- [x] done"
    html = p.parse(md)
    assert '<input type="checkbox" disabled checked>' in html
    assert "done" in html

def test_task_list_mixed():
    p = MarkdownParser()
    md = "- [ ] todo\n- [x] done\n- regular item"
    html = p.parse(md)
    assert '<input type="checkbox" disabled>' in html
    assert '<input type="checkbox" disabled checked>' in html
    assert "<li>regular item</li>" in html


# ---------------------------------------------------------------------------
# GFM Tables
# ---------------------------------------------------------------------------

def test_table_basic():
    p = MarkdownParser()
    md = "| Name | Age |\n|------|-----|\n| Alice | 30 |"
    html = p.parse(md)
    assert "<table>" in html
    assert "<thead>" in html
    assert "<tbody>" in html
    assert "<th" in html
    assert "<td" in html
    assert "Alice" in html

def test_table_alignment():
    p = MarkdownParser()
    md = "| Left | Center | Right |\n|:-----|:------:|------:|\n| a | b | c |"
    html = p.parse(md)
    assert 'style="text-align:left"' in html
    assert 'style="text-align:center"' in html
    assert 'style="text-align:right"' in html


# ---------------------------------------------------------------------------
# Hard Line Breaks
# ---------------------------------------------------------------------------

def test_hard_break_two_spaces():
    p = MarkdownParser()
    md = "line one  \nline two"
    html = p.parse(md)
    assert "<br>" in html

def test_hard_break_backslash():
    p = MarkdownParser()
    md = "line one\\\nline two"
    html = p.parse(md)
    assert "<br>" in html


# ---------------------------------------------------------------------------
# Raw HTML passthrough
# ---------------------------------------------------------------------------

def test_raw_html_div():
    p = MarkdownParser()
    md = "<div class=\"wrapper\">"
    html = p.parse(md)
    assert '<div class="wrapper">' in html

def test_raw_html_closing():
    p = MarkdownParser()
    md = "</div>"
    html = p.parse(md)
    assert "</div>" in html


# ---------------------------------------------------------------------------
# Inline Elements (STORY-003)
# ---------------------------------------------------------------------------

def test_inline_bold_stars():
    result = _process_inline("hello **world** end")
    assert "<strong>world</strong>" in result

def test_inline_bold_underscores():
    result = _process_inline("hello __world__ end")
    assert "<strong>world</strong>" in result

def test_inline_italic_star():
    result = _process_inline("hello *world* end")
    assert "<em>world</em>" in result

def test_inline_italic_underscore():
    result = _process_inline("a _word_ b")
    assert "<em>word</em>" in result

def test_inline_bold_italic():
    result = _process_inline("***bold italic***")
    assert "<strong><em>bold italic</em></strong>" in result

def test_inline_code_span():
    result = _process_inline("use `code` here")
    assert "<code>code</code>" in result

def test_inline_code_not_processed():
    # Content inside backticks should NOT be processed for Markdown
    result = _process_inline("`**not bold**`")
    assert "<strong>" not in result
    assert "**not bold**" in result or "&ast;&ast;" in result or "**not bold**" in result

def test_inline_strikethrough():
    result = _process_inline("~~deleted~~")
    assert "<del>deleted</del>" in result

def test_inline_link():
    result = _process_inline("[click here](https://example.com)")
    assert '<a href="https://example.com">click here</a>' in result

def test_inline_image_url():
    result = _process_inline("![alt text](https://example.com/img.png)")
    assert 'src="https://example.com/img.png"' in result
    assert 'alt="alt text"' in result

def test_inline_image_local_exists():
    test_dir = Path(__file__).parent
    image_path = test_dir / "test_image.png"
    source_md = test_dir / "test.md"
    result = _process_inline(f"![alt](test_image.png)", source_path=source_md)
    assert result.startswith('<img src="data:image/png;base64,')
    assert 'alt="alt"' in result

def test_inline_image_local_missing():
    test_dir = Path(__file__).parent
    source_md = test_dir / "test.md"
    result = _process_inline("![alt](./missing.png)", source_path=source_md)
    assert 'src="./missing.png"' in result

def test_inline_image_url_unchanged():
    result = _process_inline("![alt](https://example.com/img.png)")
    assert 'src="https://example.com/img.png"' in result

def test_inline_html_passthrough():
    result = _process_inline("text <br> more")
    assert "<br>" in result

def test_inline_html_not_double_escaped():
    result = _process_inline('<span class="x">text</span>')
    assert '<span class="x">' in result
    assert "&lt;span" not in result

def test_inline_html_escape_text():
    # Regular text with &, <, > should be escaped
    result = _process_inline("a & b < c > d")
    assert "&amp;" in result
    assert "&lt;" in result
    assert "&gt;" in result

def test_inline_in_paragraph():
    p = MarkdownParser()
    html = p.parse("Hello **world** and *italic*")
    assert "<strong>world</strong>" in html
    assert "<em>italic</em>" in html

def test_inline_paragraph_html_escape():
    p = MarkdownParser()
    html = p.parse("a & b < c > d")
    assert "&amp;" in html
    assert "&lt;" in html
    assert "&gt;" in html

def test_inline_bold_italic_in_paragraph():
    p = MarkdownParser()
    html = p.parse("***bold italic***")
    assert "<strong><em>bold italic</em></strong>" in html


# ---------------------------------------------------------------------------
# embed_image function tests (STORY-003)
# ---------------------------------------------------------------------------

def test_embed_image_http_passthrough():
    source = Path("/some/dir/doc.md")
    result = embed_image("http://example.com/img.png", source)
    assert result == "http://example.com/img.png"

def test_embed_image_https_passthrough():
    source = Path("/some/dir/doc.md")
    result = embed_image("https://example.com/img.png", source)
    assert result == "https://example.com/img.png"

def test_embed_image_local_exists():
    test_dir = Path(__file__).parent
    source = test_dir / "test.md"
    result = embed_image("test_image.png", source)
    assert result.startswith("data:image/png;base64,")

def test_embed_image_local_missing():
    test_dir = Path(__file__).parent
    source = test_dir / "test.md"
    result = embed_image("./missing.png", source)
    assert result == "./missing.png"

def test_embed_image_unknown_mime():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "file.unknownext12345"
        tmp_path.write_bytes(b"data")
        source = Path(tmpdir) / "doc.md"
        result = embed_image("file.unknownext12345", source)
        assert result.startswith("data:application/octet-stream;base64,")

def test_parser_with_source_path():
    test_dir = Path(__file__).parent
    source_path = test_dir / "test.md"
    p = MarkdownParser(source_path=source_path)
    html = p.parse("![img](test_image.png)")
    assert 'src="data:image/png;base64,' in html


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_functions = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for fn in test_functions:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {passed + failed} tests.")
    if failed:
        sys.exit(1)
