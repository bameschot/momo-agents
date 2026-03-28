"""
Tests for STORY-013: TocBuilder — Table of Contents Generator (md2pdf)

Tests cover build_toc() behaviour for md2pdf.py:
  - empty heading list → ""
  - single H1 → <nav id="toc"> with one <li> and correct anchor
  - H1 + H2 + H3 → correct three-level nesting
  - H2 with no preceding H1 → H2 appears at top level
  - multiple H2s under same H1 → siblings in same nested <ul>
  - duplicate slugs → both href values present
  - H4+ headings → not in ToC output
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from md2pdf import Heading, build_toc  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def h(level: int, text: str, slug: str | None = None) -> Heading:
    """Shorthand for creating a Heading."""
    if slug is None:
        slug = text.lower().replace(" ", "-")
    return Heading(level=level, text=text, slug=slug)


def assert_well_nested(html_str: str) -> None:
    """Assert that every opening tag has a matching closing tag."""
    for tag in ("ul", "li", "nav"):
        opens_bare = html_str.count(f"<{tag}>")
        opens_with_attrs = html_str.count(f"<{tag} ")
        opens = opens_bare + opens_with_attrs
        closes = html_str.count(f"</{tag}>")
        assert opens == closes, (
            f"<{tag}> opens={opens} (bare={opens_bare}, attr={opens_with_attrs}), "
            f"closes={closes} in:\n{html_str}"
        )


# ---------------------------------------------------------------------------
# Empty / no headings tests
# ---------------------------------------------------------------------------


class TestBuildTocEmpty:
    def test_empty_list_returns_empty_string(self) -> None:
        assert build_toc([]) == ""

    def test_only_h4_returns_empty_string(self) -> None:
        """H4+ headings are outside ToC scope."""
        assert build_toc([h(4, "Deep"), h(5, "Deeper"), h(6, "Deepest")]) == ""

    def test_returns_string_type(self) -> None:
        result = build_toc([])
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Nav wrapper tests
# ---------------------------------------------------------------------------


class TestBuildTocNav:
    def test_nav_id_toc_present(self) -> None:
        result = build_toc([h(1, "Intro")])
        assert '<nav id="toc">' in result
        assert "</nav>" in result

    def test_result_starts_with_nav(self) -> None:
        result = build_toc([h(1, "A")])
        assert result.startswith('<nav id="toc">')

    def test_result_ends_with_nav(self) -> None:
        result = build_toc([h(1, "A")])
        assert result.endswith("</nav>")


# ---------------------------------------------------------------------------
# Single heading tests
# ---------------------------------------------------------------------------


class TestBuildTocSingleHeading:
    def test_single_h1(self) -> None:
        result = build_toc([h(1, "Home", "home")])
        assert '<li><a href="#home">Home</a>' in result
        assert_well_nested(result)

    def test_single_h2_at_top_level(self) -> None:
        """H2 with no preceding H1 appears at top level."""
        result = build_toc([h(2, "Section", "section")])
        assert '<li><a href="#section">Section</a>' in result
        assert_well_nested(result)

    def test_single_h3_at_top_level(self) -> None:
        """H3 with no preceding headings appears at top level."""
        result = build_toc([h(3, "Sub", "sub")])
        assert '<li><a href="#sub">Sub</a>' in result
        assert_well_nested(result)


# ---------------------------------------------------------------------------
# Nesting tests
# ---------------------------------------------------------------------------


class TestBuildTocNesting:
    def test_h1_h2_nesting(self) -> None:
        headings = [h(1, "Top", "top"), h(2, "Sub", "sub")]
        result = build_toc(headings)
        assert result.index("#sub") > result.index("#top")
        assert_well_nested(result)

    def test_h1_h2_h3_deep_nesting(self) -> None:
        headings = [h(1, "H1", "h1"), h(2, "H2", "h2"), h(3, "H3", "h3")]
        result = build_toc(headings)
        assert '<a href="#h1">H1</a>' in result
        assert '<a href="#h2">H2</a>' in result
        assert '<a href="#h3">H3</a>' in result
        # Nesting: at least 3 opening <ul> tags
        assert result.count("<ul>") >= 3
        assert_well_nested(result)

    def test_h1_h2_h3_h2_h1_sequence(self) -> None:
        """Full round-trip: descend and ascend the heading hierarchy."""
        headings = [
            h(1, "Title", "title"),
            h(2, "Chapter 1", "chapter-1"),
            h(3, "Section 1.1", "section-1-1"),
            h(2, "Chapter 2", "chapter-2"),
            h(1, "Appendix", "appendix"),
        ]
        result = build_toc(headings)
        for slug in ("title", "chapter-1", "section-1-1", "chapter-2", "appendix"):
            assert f'href="#{slug}"' in result, f"Missing href for #{slug}"
        assert_well_nested(result)

    def test_h1_to_h3_level_jump(self) -> None:
        """H1 followed directly by H3 must produce valid HTML (no crash)."""
        headings = [h(1, "Top", "top"), h(3, "Deep", "deep")]
        result = build_toc(headings)
        assert '<a href="#top">Top</a>' in result
        assert '<a href="#deep">Deep</a>' in result
        assert_well_nested(result)

    def test_h3_to_h1_level_jump_up(self) -> None:
        """H3 followed by H1 should close all nested levels cleanly."""
        headings = [h(3, "Deep", "deep"), h(1, "Top", "top")]
        result = build_toc(headings)
        assert '<a href="#deep">Deep</a>' in result
        assert '<a href="#top">Top</a>' in result
        assert_well_nested(result)

    def test_multiple_h2s_under_same_h1(self) -> None:
        """Multiple H2s under same H1 appear as siblings in the same nested <ul>."""
        headings = [
            h(1, "Parent", "parent"),
            h(2, "Child A", "child-a"),
            h(2, "Child B", "child-b"),
            h(2, "Child C", "child-c"),
        ]
        result = build_toc(headings)
        assert 'href="#child-a"' in result
        assert 'href="#child-b"' in result
        assert 'href="#child-c"' in result
        # Should have exactly 2 <ul> tags: one outer, one nested under h1
        assert result.count("<ul>") == 2
        assert_well_nested(result)

    def test_alternating_levels(self) -> None:
        headings = [
            h(1, "A", "a"),
            h(2, "B", "b"),
            h(1, "C", "c"),
            h(2, "D", "d"),
            h(1, "E", "e"),
        ]
        result = build_toc(headings)
        for slug in ("a", "b", "c", "d", "e"):
            assert f'href="#{slug}"' in result
        assert_well_nested(result)


# ---------------------------------------------------------------------------
# H2 with no preceding H1
# ---------------------------------------------------------------------------


class TestBuildTocH2NoPrecedingH1:
    def test_h2_no_h1_appears_at_top_level(self) -> None:
        headings = [h(2, "First", "first"), h(2, "Second", "second")]
        result = build_toc(headings)
        assert 'href="#first"' in result
        assert 'href="#second"' in result
        # Only one <ul> at top level (no H1 to trigger nesting)
        assert result.count("<ul>") == 1
        assert_well_nested(result)

    def test_h2_then_h1(self) -> None:
        headings = [h(2, "Preamble", "preamble"), h(1, "Main", "main")]
        result = build_toc(headings)
        assert 'href="#preamble"' in result
        assert 'href="#main"' in result
        assert_well_nested(result)


# ---------------------------------------------------------------------------
# Slug / anchor tests
# ---------------------------------------------------------------------------


class TestBuildTocSlugs:
    def test_slug_used_as_href(self) -> None:
        heading = h(1, "My Heading", "my-heading")
        result = build_toc([heading])
        assert 'href="#my-heading"' in result

    def test_text_used_as_link_text(self) -> None:
        heading = h(1, "My Heading", "my-heading")
        result = build_toc([heading])
        assert ">My Heading<" in result

    def test_duplicate_slugs_both_present(self) -> None:
        """Duplicate slugs (e.g. foo and foo-2) both appear correctly."""
        headings = [
            h(1, "Section", "foo"),
            h(2, "Section Again", "foo-2"),
        ]
        result = build_toc(headings)
        assert 'href="#foo"' in result
        assert 'href="#foo-2"' in result
        assert_well_nested(result)

    def test_multiple_slugs_all_present(self) -> None:
        headings = [h(1, "Alpha", "alpha"), h(2, "Beta", "beta"), h(3, "Gamma", "gamma")]
        result = build_toc(headings)
        assert 'href="#alpha"' in result
        assert 'href="#beta"' in result
        assert 'href="#gamma"' in result


# ---------------------------------------------------------------------------
# H4+ exclusion tests
# ---------------------------------------------------------------------------


class TestBuildTocExclusion:
    def test_h4_excluded(self) -> None:
        headings = [h(1, "Visible", "visible"), h(4, "Hidden", "hidden")]
        result = build_toc(headings)
        assert 'href="#hidden"' not in result
        assert 'href="#visible"' in result

    def test_mixed_levels_only_h1_h2_h3_shown(self) -> None:
        headings = [
            h(1, "H1", "h1"),
            h(2, "H2", "h2"),
            h(3, "H3", "h3"),
            h(4, "H4", "h4"),
            h(5, "H5", "h5"),
            h(6, "H6", "h6"),
        ]
        result = build_toc(headings)
        assert 'href="#h1"' in result
        assert 'href="#h2"' in result
        assert 'href="#h3"' in result
        assert 'href="#h4"' not in result
        assert 'href="#h5"' not in result
        assert 'href="#h6"' not in result
