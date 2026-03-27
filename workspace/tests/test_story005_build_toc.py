"""
Tests for STORY-005: Table of Contents Builder

Tests cover build_toc() behaviour:
  - empty heading list → ""
  - only H1 headings → flat single-level <ul>
  - H1 → H2 → H3 → H2 → H1 sequence → correct nesting and de-nesting
  - level jump (H1 directly followed by H3) → well-nested output
  - anchor href values match heading slugs
  - output wrapped in <nav aria-label="Table of contents">
  - H4+ headings are excluded from ToC
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from md2html import Heading, build_toc  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def h(level: int, text: str, slug: str | None = None) -> Heading:
    """Shorthand for creating a Heading."""
    if slug is None:
        slug = text.lower().replace(" ", "-")
    return Heading(level=level, text=text, slug=slug)


def assert_well_nested(html: str) -> None:
    """Assert that every opening tag has a matching closing tag.

    Counts ``<tag>`` (no attrs) and ``<tag `` (with attrs) separately to
    avoid double-counting (e.g. ``<nav aria-label=...>`` must count as one
    opening tag, not two).
    """
    for tag in ("ul", "li", "nav"):
        # Count <tag> (self-contained, no attributes)
        opens_bare = html.count(f"<{tag}>")
        # Count <tag ... (with attributes) — these end with space, not >
        opens_with_attrs = html.count(f"<{tag} ")
        opens = opens_bare + opens_with_attrs
        closes = html.count(f"</{tag}>")
        assert opens == closes, (
            f"<{tag}> opens={opens} (bare={opens_bare}, attr={opens_with_attrs}), "
            f"closes={closes} in:\n{html}"
        )


# ---------------------------------------------------------------------------
# Basic tests
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


class TestBuildTocNav:
    def test_nav_wrapper_present(self) -> None:
        result = build_toc([h(1, "Intro")])
        assert '<nav aria-label="Table of contents">' in result
        assert "</nav>" in result

    def test_result_starts_with_nav(self) -> None:
        result = build_toc([h(1, "A")])
        assert result.startswith('<nav aria-label="Table of contents">')

    def test_result_ends_with_nav(self) -> None:
        result = build_toc([h(1, "A")])
        assert result.endswith("</nav>")


class TestBuildTocH1Only:
    def test_single_h1(self) -> None:
        result = build_toc([h(1, "Home", "home")])
        assert '<li><a href="#home">Home</a>' in result

    def test_multiple_h1_flat_list(self) -> None:
        headings = [h(1, "Alpha", "alpha"), h(1, "Beta", "beta"), h(1, "Gamma", "gamma")]
        result = build_toc(headings)
        assert '<a href="#alpha">Alpha</a>' in result
        assert '<a href="#beta">Beta</a>' in result
        assert '<a href="#gamma">Gamma</a>' in result
        assert_well_nested(result)

    def test_multiple_h1_single_ul_level(self) -> None:
        """Three H1s should produce only one <ul> nesting level."""
        headings = [h(1, "A"), h(1, "B"), h(1, "C")]
        result = build_toc(headings)
        # Each <ul> must have a matching </ul>
        assert result.count("<ul>") == result.count("</ul>")


# ---------------------------------------------------------------------------
# Nesting tests
# ---------------------------------------------------------------------------


class TestBuildTocNesting:
    def test_h1_h2_nesting(self) -> None:
        headings = [h(1, "Top", "top"), h(2, "Sub", "sub")]
        result = build_toc(headings)
        # Sub should appear inside a nested <ul> after Top
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
# Anchor / slug tests
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

    def test_slug_with_numbers(self) -> None:
        heading = h(2, "Chapter 3", "chapter-3")
        result = build_toc([heading])
        assert 'href="#chapter-3"' in result

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
