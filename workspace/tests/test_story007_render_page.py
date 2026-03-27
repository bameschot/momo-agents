"""
Tests for STORY-007: Page Renderer — HTML5 Document Assembly

Tests cover render_page() behaviour:
  - returns string starting with <!DOCTYPE html>
  - <title> value is correctly HTML-escaped
  - when toc_html non-empty: <aside> and <details> appear
  - when toc_html empty: <aside> and <details> do NOT appear
  - result.body_html appears inside <article>
  - STYLES content appears inside <style>
  - SCRIPTS content appears inside <script>
  - html lang="en" is present
  - charset and viewport meta tags are present
  - theme toggle button is present
  - no-flash script is in <head>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from md2html import ParseResult, render_page  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _result(body_html: str = "<p>Hello</p>", title: str | None = None) -> ParseResult:
    """Create a minimal ParseResult for testing."""
    return ParseResult(body_html=body_html, headings=[], title=title)


SAMPLE_TOC = '<nav aria-label="Table of contents"><ul><li><a href="#h1">H1</a></li></ul></nav>'


# ---------------------------------------------------------------------------
# DOCTYPE and structure
# ---------------------------------------------------------------------------


class TestDoctype:
    def test_starts_with_doctype(self) -> None:
        html = render_page(_result(), "Title", "")
        assert html.startswith("<!DOCTYPE html>")

    def test_returns_string(self) -> None:
        result = render_page(_result(), "Title", "")
        assert isinstance(result, str)

    def test_html_lang_en(self) -> None:
        html = render_page(_result(), "Title", "")
        assert 'lang="en"' in html

    def test_charset_meta(self) -> None:
        html = render_page(_result(), "Title", "")
        assert 'charset="UTF-8"' in html or "charset=UTF-8" in html

    def test_viewport_meta(self) -> None:
        html = render_page(_result(), "Title", "")
        assert "viewport" in html
        assert "width=device-width" in html

    def test_html_tag_present(self) -> None:
        html = render_page(_result(), "Title", "")
        assert "<html" in html
        assert "</html>" in html

    def test_head_present(self) -> None:
        html = render_page(_result(), "Title", "")
        assert "<head>" in html
        assert "</head>" in html

    def test_body_present(self) -> None:
        html = render_page(_result(), "Title", "")
        assert "<body>" in html or "<body" in html
        assert "</body>" in html


# ---------------------------------------------------------------------------
# Title tests
# ---------------------------------------------------------------------------


class TestTitle:
    def test_title_in_title_tag(self) -> None:
        html = render_page(_result(), "My Document", "")
        assert "<title>My Document</title>" in html

    def test_title_html_escaped_ampersand(self) -> None:
        html = render_page(_result(), "A & B", "")
        assert "<title>A &amp; B</title>" in html
        assert "<title>A & B</title>" not in html

    def test_title_html_escaped_lt(self) -> None:
        html = render_page(_result(), "<script>", "")
        assert "&lt;script&gt;" in html
        assert "<title><script></title>" not in html

    def test_title_html_escaped_gt(self) -> None:
        html = render_page(_result(), "a > b", "")
        assert "a &gt; b" in html

    def test_plain_title_not_double_escaped(self) -> None:
        html = render_page(_result(), "Simple Title", "")
        assert "<title>Simple Title</title>" in html


# ---------------------------------------------------------------------------
# Styles and scripts
# ---------------------------------------------------------------------------


class TestStylesScripts:
    def test_styles_in_style_tag(self) -> None:
        html = render_page(_result(), "T", "")
        assert "<style>" in html
        assert "</style>" in html
        # STYLES content appears between <style> tags
        style_start = html.index("<style>") + len("<style>")
        style_end = html.index("</style>")
        style_content = html[style_start:style_end]
        # At least part of STYLES must be present
        assert "prefers-color-scheme" in style_content

    def test_scripts_in_script_tag(self) -> None:
        html = render_page(_result(), "T", "")
        # Find a <script> that contains our JS (not the no-flash one)
        assert "localStorage" in html
        assert "DOMContentLoaded" in html

    def test_no_flash_script_in_head(self) -> None:
        html = render_page(_result(), "T", "")
        head_end = html.index("</head>")
        head = html[:head_end]
        # No-flash snippet reads localStorage before paint
        assert "localStorage" in head

    def test_styles_content_present(self) -> None:
        html = render_page(_result(), "T", "")
        # A distinctive piece of our CSS
        assert "data-theme" in html

    def test_scripts_content_present(self) -> None:
        html = render_page(_result(), "T", "")
        assert "Copied!" in html


# ---------------------------------------------------------------------------
# Body HTML / article
# ---------------------------------------------------------------------------


class TestBodyHtml:
    def test_body_html_in_article(self) -> None:
        body = "<p>Hello World</p>"
        html = render_page(ParseResult(body_html=body, headings=[], title=None), "T", "")
        assert "<article>" in html
        assert "</article>" in html
        assert body in html

    def test_body_html_between_article_tags(self) -> None:
        body = "<p>Unique Content XYZ</p>"
        html = render_page(ParseResult(body_html=body, headings=[], title=None), "T", "")
        art_start = html.index("<article>") + len("<article>")
        art_end = html.index("</article>")
        article_content = html[art_start:art_end]
        assert "Unique Content XYZ" in article_content

    def test_empty_body_html(self) -> None:
        html = render_page(ParseResult(body_html="", headings=[], title=None), "T", "")
        assert "<article></article>" in html or "<article>" in html

    def test_main_element_present(self) -> None:
        html = render_page(_result(), "T", "")
        assert "<main>" in html or "<main" in html


# ---------------------------------------------------------------------------
# ToC conditional rendering
# ---------------------------------------------------------------------------


class TestTocRendering:
    def test_nonempty_toc_shows_aside(self) -> None:
        html = render_page(_result(), "T", SAMPLE_TOC)
        assert "<aside" in html

    def test_nonempty_toc_shows_details(self) -> None:
        html = render_page(_result(), "T", SAMPLE_TOC)
        assert "<details" in html

    def test_nonempty_toc_shows_summary(self) -> None:
        html = render_page(_result(), "T", SAMPLE_TOC)
        assert "<summary" in html

    def test_nonempty_toc_contains_nav(self) -> None:
        html = render_page(_result(), "T", SAMPLE_TOC)
        assert SAMPLE_TOC in html

    def test_empty_toc_no_aside(self) -> None:
        html = render_page(_result(), "T", "")
        assert "<aside" not in html

    def test_empty_toc_no_details(self) -> None:
        html = render_page(_result(), "T", "")
        assert "<details" not in html


# ---------------------------------------------------------------------------
# Theme toggle button
# ---------------------------------------------------------------------------


class TestThemeToggle:
    def test_theme_toggle_button_present(self) -> None:
        html = render_page(_result(), "T", "")
        assert 'id="theme-toggle"' in html

    def test_theme_toggle_is_button(self) -> None:
        html = render_page(_result(), "T", "")
        toggle_idx = html.index('id="theme-toggle"')
        # The tag before the id attribute should start with <button
        surrounding = html[max(0, toggle_idx - 10):toggle_idx]
        assert "button" in surrounding or "<button" in html

    def test_header_present(self) -> None:
        html = render_page(_result(), "T", "")
        assert "<header>" in html or "<header" in html
