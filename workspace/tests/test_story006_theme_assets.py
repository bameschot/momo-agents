"""
Tests for STORY-006: Theme Assets — Inlined CSS and JavaScript

Tests verify that STYLES and SCRIPTS constants exist, are non-empty strings,
and contain the required key tokens specified by the acceptance criteria.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from md2html import CSS, JS, SCRIPTS, STYLES  # noqa: E402

# ---------------------------------------------------------------------------
# STYLES constant tests
# ---------------------------------------------------------------------------


class TestStyles:
    def test_styles_is_string(self) -> None:
        assert isinstance(STYLES, str)

    def test_styles_is_nonempty(self) -> None:
        assert len(STYLES.strip()) > 0

    def test_styles_contains_dark_media_query(self) -> None:
        assert "@media (prefers-color-scheme: dark)" in STYLES

    def test_styles_contains_mobile_media_query(self) -> None:
        assert "@media (max-width: 768px)" in STYLES

    def test_styles_contains_data_theme(self) -> None:
        assert "data-theme" in STYLES

    def test_styles_contains_pre(self) -> None:
        assert "pre" in STYLES

    def test_styles_contains_table(self) -> None:
        assert "table" in STYLES

    def test_styles_light_theme_variables(self) -> None:
        """Light theme should define CSS custom properties."""
        assert "--bg:" in STYLES
        assert "--text:" in STYLES

    def test_styles_dark_theme_section(self) -> None:
        """There should be an explicit dark theme override block."""
        assert '[data-theme="dark"]' in STYLES

    def test_styles_mobile_hides_sidebar(self) -> None:
        """Mobile layout should suppress the sidebar."""
        assert "#toc-sidebar" in STYLES

    def test_styles_mobile_shows_details(self) -> None:
        """Mobile layout should reveal the mobile ToC element."""
        assert "#toc-mobile" in STYLES

    def test_styles_code_block_styling(self) -> None:
        """Code blocks need overflow-x scroll for long lines."""
        assert "overflow-x" in STYLES

    def test_styles_blockquote(self) -> None:
        assert "blockquote" in STYLES

    def test_styles_horizontal_rule(self) -> None:
        assert "hr" in STYLES

    def test_styles_focus_outline_not_removed(self) -> None:
        """Focus styles must be present (accessibility)."""
        assert "focus-visible" in STYLES or "focus" in STYLES

    def test_styles_copy_btn(self) -> None:
        """Copy button class must be styled."""
        assert ".copy-btn" in STYLES


# ---------------------------------------------------------------------------
# SCRIPTS constant tests
# ---------------------------------------------------------------------------


class TestScripts:
    def test_scripts_is_string(self) -> None:
        assert isinstance(SCRIPTS, str)

    def test_scripts_is_nonempty(self) -> None:
        assert len(SCRIPTS.strip()) > 0

    def test_scripts_contains_localstorage(self) -> None:
        assert "localStorage" in SCRIPTS

    def test_scripts_contains_copied(self) -> None:
        assert "Copied!" in SCRIPTS

    def test_scripts_contains_clipboard(self) -> None:
        assert "navigator.clipboard" in SCRIPTS

    def test_scripts_contains_domcontentloaded(self) -> None:
        assert "DOMContentLoaded" in SCRIPTS

    def test_scripts_contains_theme_toggle(self) -> None:
        assert "theme-toggle" in SCRIPTS

    def test_scripts_contains_theme_storage_key(self) -> None:
        assert "md2html-theme" in SCRIPTS

    def test_scripts_contains_queryselectorall_pre(self) -> None:
        assert "querySelectorAll" in SCRIPTS

    def test_scripts_no_eval(self) -> None:
        """JS must not use eval()."""
        # Ensure 'eval(' doesn't appear (allow 'evaluate' etc.)
        import re
        assert not re.search(r'\beval\s*\(', SCRIPTS)

    def test_scripts_iife_wrapper(self) -> None:
        """Should be wrapped in an IIFE for encapsulation."""
        assert "(function" in SCRIPTS or "(() =>" in SCRIPTS


# ---------------------------------------------------------------------------
# Backward-compat alias tests
# ---------------------------------------------------------------------------


class TestAliases:
    def test_css_alias_equals_styles(self) -> None:
        """CSS should be an alias (or equal) to STYLES."""
        assert CSS == STYLES

    def test_js_alias_equals_scripts(self) -> None:
        """JS should be an alias (or equal) to SCRIPTS."""
        assert JS == SCRIPTS

    def test_css_nonempty(self) -> None:
        assert len(CSS.strip()) > 0

    def test_js_nonempty(self) -> None:
        assert len(JS.strip()) > 0
