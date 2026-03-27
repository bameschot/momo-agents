"""
Tests for STORY-002: Block-Level Markdown Parser

Tests cover:
  - ATX headings (H1–H6), slug generation, H1–H3 in headings, H4–H6 excluded
  - Duplicate heading slugs get numeric suffixes
  - Fenced code blocks with/without language tag, HTML-escaping inside
  - Blockquotes (single and multi-line)
  - Unordered lists (single-level and nested)
  - Ordered lists (single-level and nested)
  - Tables with left/center/right alignment
  - Malformed table (column count mismatch) → <pre>
  - Horizontal rules
  - Paragraphs
  - ParseResult.title (first H1 text or None)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from md2html import Heading, ParseResult, convert, slugify  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def base_dir(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# slugify helper
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_lowercase(self) -> None:
        assert slugify("Hello World") == "hello-world"

    def test_spaces_to_hyphens(self) -> None:
        assert slugify("foo bar baz") == "foo-bar-baz"

    def test_strips_non_alphanumeric(self) -> None:
        assert slugify("Hello, World!") == "hello-world"

    def test_preserves_hyphens(self) -> None:
        assert slugify("pre-existing") == "pre-existing"

    def test_multiple_spaces(self) -> None:
        assert slugify("a  b") == "a-b"

    def test_empty(self) -> None:
        assert slugify("") == ""


# ---------------------------------------------------------------------------
# ATX Headings
# ---------------------------------------------------------------------------


class TestHeadings:
    def test_h1(self, base_dir: Path) -> None:
        result = convert("# Hello World\n", base_dir)
        assert '<h1 id="hello-world">Hello World</h1>' in result.body_html

    def test_h2(self, base_dir: Path) -> None:
        result = convert("## Section Two\n", base_dir)
        assert '<h2 id="section-two">Section Two</h2>' in result.body_html

    def test_h3(self, base_dir: Path) -> None:
        result = convert("### Sub Section\n", base_dir)
        assert '<h3 id="sub-section">Sub Section</h3>' in result.body_html

    def test_h4_in_body_not_in_headings(self, base_dir: Path) -> None:
        result = convert("#### Deep\n", base_dir)
        assert '<h4 id="deep">Deep</h4>' in result.body_html
        assert result.headings == []

    def test_h5_in_body_not_in_headings(self, base_dir: Path) -> None:
        result = convert("##### Deeper\n", base_dir)
        assert '<h5 id="deeper">Deeper</h5>' in result.body_html
        assert result.headings == []

    def test_h6_in_body_not_in_headings(self, base_dir: Path) -> None:
        result = convert("###### Deepest\n", base_dir)
        assert '<h6 id="deepest">Deepest</h6>' in result.body_html
        assert result.headings == []

    def test_h1_collected_in_headings(self, base_dir: Path) -> None:
        result = convert("# Title\n", base_dir)
        assert len(result.headings) == 1
        assert result.headings[0] == Heading(level=1, text="Title", slug="title")

    def test_h2_collected_in_headings(self, base_dir: Path) -> None:
        result = convert("## Subtitle\n", base_dir)
        assert len(result.headings) == 1
        assert result.headings[0].level == 2

    def test_h3_collected_in_headings(self, base_dir: Path) -> None:
        result = convert("### Sub\n", base_dir)
        assert len(result.headings) == 1
        assert result.headings[0].level == 3

    def test_multiple_headings_order(self, base_dir: Path) -> None:
        md = "# First\n\n## Second\n\n### Third\n"
        result = convert(md, base_dir)
        assert len(result.headings) == 3
        assert result.headings[0].level == 1
        assert result.headings[1].level == 2
        assert result.headings[2].level == 3

    def test_duplicate_slugs_get_suffixes(self, base_dir: Path) -> None:
        md = "# Intro\n\n# Intro\n\n# Intro\n"
        result = convert(md, base_dir)
        slugs = [h.slug for h in result.headings]
        assert slugs[0] == "intro"
        assert slugs[1] == "intro-2"
        assert slugs[2] == "intro-3"

    def test_duplicate_slug_ids_in_html(self, base_dir: Path) -> None:
        md = "# Same\n\n# Same\n"
        result = convert(md, base_dir)
        assert 'id="same"' in result.body_html
        assert 'id="same-2"' in result.body_html


# ---------------------------------------------------------------------------
# ParseResult.title
# ---------------------------------------------------------------------------


class TestParseResultTitle:
    def test_title_from_first_h1(self, base_dir: Path) -> None:
        result = convert("# My Title\n\n## Section\n", base_dir)
        assert result.title == "My Title"

    def test_title_none_when_no_h1(self, base_dir: Path) -> None:
        result = convert("## Section\n\n### Sub\n", base_dir)
        assert result.title is None

    def test_title_is_first_h1_only(self, base_dir: Path) -> None:
        result = convert("# First\n\n# Second\n", base_dir)
        assert result.title == "First"

    def test_title_none_on_empty(self, base_dir: Path) -> None:
        result = convert("", base_dir)
        assert result.title is None


# ---------------------------------------------------------------------------
# Fenced Code Blocks
# ---------------------------------------------------------------------------


class TestFencedCodeBlocks:
    def test_with_language_tag(self, base_dir: Path) -> None:
        md = "```python\nprint(1 + 2)\n```\n"
        result = convert(md, base_dir)
        assert '<pre><code class="language-python">print(1 + 2)</code></pre>' in result.body_html

    def test_without_language_tag(self, base_dir: Path) -> None:
        md = "```\nhello world\n```\n"
        result = convert(md, base_dir)
        assert '<pre><code>hello world</code></pre>' in result.body_html

    def test_html_escape_inside_code_block(self, base_dir: Path) -> None:
        md = "```\n<b>bold</b> & \"quotes\"\n```\n"
        result = convert(md, base_dir)
        assert '&lt;b&gt;bold&lt;/b&gt; &amp; &quot;quotes&quot;' in result.body_html

    def test_no_inline_processing_inside_fence(self, base_dir: Path) -> None:
        # Bold markers should not be processed inside code blocks
        md = "```\n**not bold**\n```\n"
        result = convert(md, base_dir)
        assert '**not bold**' in result.body_html

    def test_multiline_code_block(self, base_dir: Path) -> None:
        md = "```js\nconst x = 1;\nconst y = 2;\n```\n"
        result = convert(md, base_dir)
        assert 'const x = 1;\nconst y = 2;' in result.body_html


# ---------------------------------------------------------------------------
# Blockquotes
# ---------------------------------------------------------------------------


class TestBlockquotes:
    def test_single_line_blockquote(self, base_dir: Path) -> None:
        md = "> This is a quote\n"
        result = convert(md, base_dir)
        assert '<blockquote><p>This is a quote</p></blockquote>' in result.body_html

    def test_multi_line_blockquote_joined(self, base_dir: Path) -> None:
        md = "> Line one\n> Line two\n"
        result = convert(md, base_dir)
        assert '<blockquote>' in result.body_html
        assert 'Line one' in result.body_html
        assert 'Line two' in result.body_html
        # Should be a single blockquote
        assert result.body_html.count('<blockquote>') == 1


# ---------------------------------------------------------------------------
# Unordered Lists
# ---------------------------------------------------------------------------


class TestUnorderedLists:
    def test_simple_ul(self, base_dir: Path) -> None:
        md = "- Item A\n- Item B\n- Item C\n"
        result = convert(md, base_dir)
        assert '<ul>' in result.body_html
        assert '<li>Item A' in result.body_html
        assert '<li>Item B' in result.body_html
        assert '<li>Item C' in result.body_html

    def test_ul_with_asterisk(self, base_dir: Path) -> None:
        md = "* One\n* Two\n"
        result = convert(md, base_dir)
        assert '<ul>' in result.body_html
        assert '<li>One' in result.body_html

    def test_ul_with_plus(self, base_dir: Path) -> None:
        md = "+ Alpha\n+ Beta\n"
        result = convert(md, base_dir)
        assert '<ul>' in result.body_html
        assert '<li>Alpha' in result.body_html

    def test_nested_ul_two_levels(self, base_dir: Path) -> None:
        md = "- Parent\n  - Child\n"
        result = convert(md, base_dir)
        # Should have nested <ul>
        assert result.body_html.count('<ul>') == 2
        assert '<li>Parent' in result.body_html
        assert '<li>Child' in result.body_html


# ---------------------------------------------------------------------------
# Ordered Lists
# ---------------------------------------------------------------------------


class TestOrderedLists:
    def test_simple_ol(self, base_dir: Path) -> None:
        md = "1. First\n2. Second\n3. Third\n"
        result = convert(md, base_dir)
        assert '<ol>' in result.body_html
        assert '<li>First' in result.body_html
        assert '<li>Second' in result.body_html

    def test_nested_ol_two_levels(self, base_dir: Path) -> None:
        md = "1. Parent\n   1. Child\n"
        result = convert(md, base_dir)
        assert result.body_html.count('<ol>') == 2
        assert '<li>Parent' in result.body_html
        assert '<li>Child' in result.body_html


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class TestTables:
    def test_simple_table(self, base_dir: Path) -> None:
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n"
        result = convert(md, base_dir)
        assert '<table>' in result.body_html
        assert '<thead>' in result.body_html
        assert '<tbody>' in result.body_html
        assert '<th>' in result.body_html or '<th ' in result.body_html

    def test_alignment(self, base_dir: Path) -> None:
        md = "| Left | Center | Right |\n|:---|:---:|---:|\n| a | b | c |\n"
        result = convert(md, base_dir)
        assert 'text-align: left' in result.body_html
        assert 'text-align: center' in result.body_html
        assert 'text-align: right' in result.body_html

    def test_malformed_table_fallback_to_pre(self, base_dir: Path) -> None:
        # Header has 3 cols, separator has 3, but body row has 2 — malformed
        md = "| A | B | C |\n|---|---|---|\n| 1 | 2 |\n"
        result = convert(md, base_dir)
        assert '<pre>' in result.body_html
        assert '<table>' not in result.body_html

    def test_malformed_table_sep_mismatch(self, base_dir: Path) -> None:
        # Header has 2 cols, separator has 3 — malformed
        md = "| A | B |\n|---|---|---|\n| 1 | 2 |\n"
        result = convert(md, base_dir)
        assert '<pre>' in result.body_html
        assert '<table>' not in result.body_html

    def test_table_no_alignment(self, base_dir: Path) -> None:
        md = "| X | Y |\n|---|---|\n| p | q |\n"
        result = convert(md, base_dir)
        # th/td should not have a style attribute when alignment is absent
        assert '<th>X</th>' in result.body_html or '<th>X' in result.body_html


# ---------------------------------------------------------------------------
# Horizontal Rules
# ---------------------------------------------------------------------------


class TestHorizontalRules:
    def test_hr_dashes(self, base_dir: Path) -> None:
        result = convert("---\n", base_dir)
        assert '<hr>' in result.body_html

    def test_hr_asterisks(self, base_dir: Path) -> None:
        result = convert("***\n", base_dir)
        assert '<hr>' in result.body_html

    def test_hr_underscores(self, base_dir: Path) -> None:
        result = convert("___\n", base_dir)
        assert '<hr>' in result.body_html

    def test_hr_with_spaces(self, base_dir: Path) -> None:
        result = convert("---   \n", base_dir)
        assert '<hr>' in result.body_html


# ---------------------------------------------------------------------------
# Paragraphs
# ---------------------------------------------------------------------------


class TestParagraphs:
    def test_simple_paragraph(self, base_dir: Path) -> None:
        result = convert("Hello world.\n", base_dir)
        assert '<p>Hello world.</p>' in result.body_html

    def test_multiple_paragraphs(self, base_dir: Path) -> None:
        md = "First para.\n\nSecond para.\n"
        result = convert(md, base_dir)
        assert '<p>First para.</p>' in result.body_html
        assert '<p>Second para.</p>' in result.body_html

    def test_multiline_paragraph_joined(self, base_dir: Path) -> None:
        md = "Line one\nLine two\nLine three\n"
        result = convert(md, base_dir)
        assert '<p>' in result.body_html
        assert 'Line one' in result.body_html
        assert 'Line two' in result.body_html


# ---------------------------------------------------------------------------
# convert() return type
# ---------------------------------------------------------------------------


class TestConvertReturnType:
    def test_returns_parse_result(self, base_dir: Path) -> None:
        result = convert("# Title\n", base_dir)
        assert isinstance(result, ParseResult)

    def test_body_html_is_str(self, base_dir: Path) -> None:
        result = convert("# Title\n", base_dir)
        assert isinstance(result.body_html, str)

    def test_headings_is_list(self, base_dir: Path) -> None:
        result = convert("# Title\n", base_dir)
        assert isinstance(result.headings, list)

    def test_empty_markdown(self, base_dir: Path) -> None:
        result = convert("", base_dir)
        assert isinstance(result, ParseResult)
        assert result.body_html == ""
        assert result.headings == []
        assert result.title is None
