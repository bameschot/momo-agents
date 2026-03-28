"""
Tests for STORY-011: MarkdownParser — Block-Level Parsing

Tests each block type in isolation using convert(text, Path(".")).
Inline formatting is not expected — bold, links, etc. may appear as raw text
(HTML-escaped). Phase 2 inline rendering is covered by STORY-012.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from md2pdf import convert, Heading, ParseResult


BASE_DIR = Path(".")


# ---------------------------------------------------------------------------
# Headings
# ---------------------------------------------------------------------------


def test_h1_tag():
    result = convert("# Hello World", BASE_DIR)
    assert "<h1" in result.body_html
    assert "Hello World" in result.body_html


def test_h2_tag():
    result = convert("## Section", BASE_DIR)
    assert "<h2" in result.body_html


def test_h3_tag():
    result = convert("### Sub", BASE_DIR)
    assert "<h3" in result.body_html


def test_h4_tag():
    result = convert("#### Deep", BASE_DIR)
    assert "<h4" in result.body_html


def test_h5_tag():
    result = convert("##### Deeper", BASE_DIR)
    assert "<h5" in result.body_html


def test_h6_tag():
    result = convert("###### Deepest", BASE_DIR)
    assert "<h6" in result.body_html


def test_h1_sets_title():
    result = convert("# My Title", BASE_DIR)
    assert result.title == "My Title"


def test_no_h1_title_is_none():
    result = convert("## Section Only", BASE_DIR)
    assert result.title is None


def test_first_h1_sets_title():
    md = "# First\n\n# Second"
    result = convert(md, BASE_DIR)
    assert result.title == "First"


def test_h1_in_headings_list():
    result = convert("# Top", BASE_DIR)
    assert any(h.level == 1 and h.text == "Top" for h in result.headings)


def test_h2_in_headings_list():
    result = convert("## Section", BASE_DIR)
    assert any(h.level == 2 and h.text == "Section" for h in result.headings)


def test_h3_in_headings_list():
    result = convert("### Subsection", BASE_DIR)
    assert any(h.level == 3 and h.text == "Subsection" for h in result.headings)


def test_h4_not_in_headings_list():
    result = convert("#### Deep", BASE_DIR)
    assert not any(h.level == 4 for h in result.headings)


def test_h5_not_in_headings_list():
    result = convert("##### Deeper", BASE_DIR)
    assert not any(h.level == 5 for h in result.headings)


def test_h6_not_in_headings_list():
    result = convert("###### Deepest", BASE_DIR)
    assert not any(h.level == 6 for h in result.headings)


def test_heading_slug_in_id_attribute():
    result = convert("## Hello World", BASE_DIR)
    assert 'id="hello-world"' in result.body_html


def test_heading_slug_text():
    result = convert("## Hello World", BASE_DIR)
    assert result.headings[0].slug == "hello-world"


def test_duplicate_h2_slugs():
    """First duplicate gets base slug; second gets slug-2."""
    md = "## Foo\n\n## Foo"
    result = convert(md, BASE_DIR)
    slugs = [h.slug for h in result.headings]
    assert "foo" in slugs
    assert "foo-2" in slugs


def test_duplicate_slug_ids_in_html():
    md = "## Foo\n\n## Foo"
    result = convert(md, BASE_DIR)
    assert 'id="foo"' in result.body_html
    assert 'id="foo-2"' in result.body_html


# ---------------------------------------------------------------------------
# Fenced code blocks
# ---------------------------------------------------------------------------


def test_fenced_code_pre_code_tags():
    md = "```\nprint('hello')\n```"
    result = convert(md, BASE_DIR)
    assert "<pre><code>" in result.body_html
    assert "</code></pre>" in result.body_html


def test_fenced_code_html_escaped():
    md = "```\n<script>alert(1)</script>\n```"
    result = convert(md, BASE_DIR)
    assert "&lt;script&gt;" in result.body_html
    assert "<script>" not in result.body_html


def test_fenced_code_with_language():
    md = "```python\npass\n```"
    result = convert(md, BASE_DIR)
    assert 'class="language-python"' in result.body_html


def test_fenced_code_content_preserved():
    md = "```\nline1\nline2\n```"
    result = convert(md, BASE_DIR)
    assert "line1" in result.body_html
    assert "line2" in result.body_html


# ---------------------------------------------------------------------------
# Blockquotes
# ---------------------------------------------------------------------------


def test_blockquote_tag():
    result = convert("> This is a quote", BASE_DIR)
    assert "<blockquote>" in result.body_html
    assert "</blockquote>" in result.body_html


def test_blockquote_paragraph_inside():
    result = convert("> quote text", BASE_DIR)
    assert "<blockquote><p>" in result.body_html


def test_blockquote_consecutive_lines_merged():
    md = "> line one\n> line two"
    result = convert(md, BASE_DIR)
    # Should produce a single blockquote, not two
    assert result.body_html.count("<blockquote>") == 1
    assert "line one" in result.body_html
    assert "line two" in result.body_html


# ---------------------------------------------------------------------------
# Unordered lists
# ---------------------------------------------------------------------------


def test_unordered_list_ul_tag():
    result = convert("- item", BASE_DIR)
    assert "<ul>" in result.body_html
    assert "<li>" in result.body_html


def test_unordered_list_star_prefix():
    result = convert("* item", BASE_DIR)
    assert "<ul>" in result.body_html


def test_unordered_list_plus_prefix():
    result = convert("+ item", BASE_DIR)
    assert "<ul>" in result.body_html


def test_unordered_list_nesting():
    md = "- parent\n  - child"
    result = convert(md, BASE_DIR)
    # Should have nested ul
    assert result.body_html.count("<ul>") == 2
    assert "parent" in result.body_html
    assert "child" in result.body_html


# ---------------------------------------------------------------------------
# Ordered lists
# ---------------------------------------------------------------------------


def test_ordered_list_ol_tag():
    result = convert("1. item", BASE_DIR)
    assert "<ol>" in result.body_html
    assert "<li>" in result.body_html


def test_ordered_list_nesting():
    md = "1. parent\n  1. child"
    result = convert(md, BASE_DIR)
    assert result.body_html.count("<ol>") == 2
    assert "parent" in result.body_html
    assert "child" in result.body_html


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def test_table_structure():
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    result = convert(md, BASE_DIR)
    assert "<table>" in result.body_html
    assert "<thead>" in result.body_html
    assert "<tbody>" in result.body_html
    assert "</table>" in result.body_html


def test_table_header_cells():
    md = "| Name | Age |\n|------|-----|\n| Bob  | 30  |"
    result = convert(md, BASE_DIR)
    assert "<th" in result.body_html
    assert "Name" in result.body_html
    assert "Age" in result.body_html


def test_table_body_cells():
    md = "| Name | Age |\n|------|-----|\n| Alice | 25 |"
    result = convert(md, BASE_DIR)
    assert "<td" in result.body_html
    assert "Alice" in result.body_html
    assert "25" in result.body_html


def test_table_alignment_center():
    md = "| A |\n|:---:|\n| 1 |"
    result = convert(md, BASE_DIR)
    assert 'text-align: center' in result.body_html


def test_table_alignment_right():
    md = "| A |\n|---:|\n| 1 |"
    result = convert(md, BASE_DIR)
    assert 'text-align: right' in result.body_html


def test_table_alignment_left():
    md = "| A |\n|:---|\n| 1 |"
    result = convert(md, BASE_DIR)
    assert 'text-align: left' in result.body_html


# ---------------------------------------------------------------------------
# Horizontal rules
# ---------------------------------------------------------------------------


def test_hr_three_dashes():
    result = convert("---", BASE_DIR)
    assert "<hr>" in result.body_html


def test_hr_three_stars():
    result = convert("***", BASE_DIR)
    assert "<hr>" in result.body_html


def test_hr_three_underscores():
    result = convert("___", BASE_DIR)
    assert "<hr>" in result.body_html


# ---------------------------------------------------------------------------
# Paragraphs
# ---------------------------------------------------------------------------


def test_paragraph_tag():
    result = convert("This is a paragraph.", BASE_DIR)
    assert "<p>" in result.body_html
    assert "This is a paragraph." in result.body_html


def test_blank_lines_separate_paragraphs():
    md = "First paragraph.\n\nSecond paragraph."
    result = convert(md, BASE_DIR)
    assert result.body_html.count("<p>") == 2


def test_paragraph_html_escaping():
    result = convert("a < b & c > d", BASE_DIR)
    assert "&lt;" in result.body_html
    assert "&amp;" in result.body_html
    assert "&gt;" in result.body_html


# ---------------------------------------------------------------------------
# HTML escaping in headings
# ---------------------------------------------------------------------------


def test_heading_html_escaping():
    result = convert("# Title <em>test</em> & more", BASE_DIR)
    assert "&lt;em&gt;" in result.body_html
    assert "&amp;" in result.body_html


# ---------------------------------------------------------------------------
# ParseResult structure
# ---------------------------------------------------------------------------


def test_convert_returns_parse_result():
    result = convert("# Hello", BASE_DIR)
    assert isinstance(result, ParseResult)
    assert isinstance(result.body_html, str)
    assert isinstance(result.headings, list)


def test_empty_markdown():
    result = convert("", BASE_DIR)
    assert result.body_html == ""
    assert result.headings == []
    assert result.title is None
