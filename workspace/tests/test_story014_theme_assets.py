"""
Tests for STORY-014: ThemeAssets & PageRenderer — CSS and HTML Template (md2pdf)

Tests cover:
  - STYLES constant has non-empty CSS content
  - STYLES does not contain dark theme or theme-toggle styles
  - STYLES contains @media print rules
  - STYLES contains #toc sidebar styles
  - STYLES contains page-break-inside: avoid for pre/table
  - render_page() returns complete HTML5 document with correct structure
  - render_page() with toc_html="" omits the sidebar
  - render_page() with non-empty toc_html includes the toc content
  - No theme-toggle <button> element present
  - No external stylesheet or script references
  - <title> reflects the title parameter exactly
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from md2pdf import STYLES, Heading, ParseResult, render_page  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_result(body_html: str = "<p>Hello</p>") -> ParseResult:
    return ParseResult(
        body_html=body_html,
        headings=[],
        title=None,
    )


# ---------------------------------------------------------------------------
# STYLES tests
# ---------------------------------------------------------------------------


class TestStyles:
    def test_styles_is_nonempty_string(self) -> None:
        assert isinstance(STYLES, str)
        assert len(STYLES.strip()) > 0

    def test_no_dark_theme_block(self) -> None:
        assert '[data-theme="dark"]' not in STYLES
        assert "[data-theme='dark']" not in STYLES

    def test_no_prefers_color_scheme_dark(self) -> None:
        assert "prefers-color-scheme: dark" not in STYLES
        assert "prefers-color-scheme:dark" not in STYLES

    def test_has_media_print(self) -> None:
        assert "@media print" in STYLES

    def test_has_toc_sidebar_styles(self) -> None:
        assert "#toc" in STYLES

    def test_pre_has_page_break_inside_avoid(self) -> None:
        assert "page-break-inside: avoid" in STYLES

    def test_no_theme_toggle_styles(self) -> None:
        assert "#theme-toggle" not in STYLES

    def test_has_light_theme_variables(self) -> None:
        # Light theme variables should be present
        assert "--bg" in STYLES
        assert "--text" in STYLES

    def test_has_layout_styles(self) -> None:
        assert ".page-wrapper" in STYLES
        assert "flex" in STYLES


# ---------------------------------------------------------------------------
# render_page() structure tests
# ---------------------------------------------------------------------------


class TestRenderPage:
    def test_returns_string(self) -> None:
        result = render_page(make_result(), "Test", "")
        assert isinstance(result, str)

    def test_starts_with_doctype(self) -> None:
        result = render_page(make_result(), "Test", "")
        assert result.startswith("<!DOCTYPE html>")

    def test_has_html_wrapper(self) -> None:
        result = render_page(make_result(), "Test", "")
        assert result.count("<html") == 1
        assert result.count("</html>") == 1

    def test_has_head_body(self) -> None:
        result = render_page(make_result(), "Test", "")
        assert "<head>" in result
        assert "</head>" in result
        assert "<body>" in result
        assert "</body>" in result

    def test_title_set_correctly(self) -> None:
        result = render_page(make_result(), "My Fancy Title", "")
        assert "<title>My Fancy Title</title>" in result

    def test_title_html_escaped(self) -> None:
        result = render_page(make_result(), "A & B <C>", "")
        assert "<title>A &amp; B &lt;C&gt;</title>" in result

    def test_style_block_contains_styles(self) -> None:
        result = render_page(make_result(), "Test", "")
        assert "<style>" in result
        assert "</style>" in result
        # Should contain actual CSS content from STYLES
        assert "flex" in result or "margin" in result

    def test_body_html_included(self) -> None:
        result = render_page(make_result("<p>Content goes here</p>"), "Test", "")
        assert "<p>Content goes here</p>" in result

    def test_no_theme_toggle_button(self) -> None:
        result = render_page(make_result(), "Test", "")
        assert "theme-toggle" not in result
        # No button element that is a theme toggle
        assert 'id="theme-toggle"' not in result

    def test_no_external_stylesheets(self) -> None:
        result = render_page(make_result(), "Test", "")
        assert '<link rel="stylesheet"' not in result
        assert "<link href=" not in result

    def test_no_external_scripts(self) -> None:
        result = render_page(make_result(), "Test", "")
        assert '<script src=' not in result

    def test_fully_self_contained(self) -> None:
        """No external references at all."""
        result = render_page(make_result(), "Test", "")
        assert "http://" not in result or "data:" in result  # only data URIs
        # No external hrefs in link tags
        assert '<link' not in result


# ---------------------------------------------------------------------------
# render_page() ToC / sidebar tests
# ---------------------------------------------------------------------------


class TestRenderPageToc:
    def test_toc_html_included_when_nonempty(self) -> None:
        toc_html = '<nav id="toc"><ul><li><a href="#h1">H1</a></li></ul></nav>'
        result = render_page(make_result(), "Test", toc_html)
        assert toc_html in result

    def test_sidebar_present_when_toc_nonempty(self) -> None:
        toc_html = '<nav id="toc"><ul><li><a href="#h1">H1</a></li></ul></nav>'
        result = render_page(make_result(), "Test", toc_html)
        assert "toc-sidebar" in result

    def test_sidebar_absent_when_toc_empty(self) -> None:
        result = render_page(make_result(), "Test", "")
        assert "toc-sidebar" not in result

    def test_toc_content_absent_when_empty(self) -> None:
        result = render_page(make_result(), "Test", "")
        assert '<nav id="toc">' not in result


# ---------------------------------------------------------------------------
# render_page() no dark theme tests
# ---------------------------------------------------------------------------


class TestRenderPageNoDarkTheme:
    def test_no_data_theme_dark(self) -> None:
        result = render_page(make_result(), "Test", "")
        assert '[data-theme' not in result

    def test_no_dark_keyword_in_styles(self) -> None:
        result = render_page(make_result(), "Test", "")
        # The word "dark" should not appear in the style block
        style_start = result.index("<style>")
        style_end = result.index("</style>")
        style_content = result[style_start:style_end]
        assert "dark" not in style_content
