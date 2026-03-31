"""Tests for HTML generation and Chart.js bundle fetching."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
from token_report import generate_html, get_chartjs_source, render_summary_table


def test_get_chartjs_source_from_cache() -> None:
    """When cache exists, get_chartjs_source returns cache without network call."""
    dummy_js = "/*! Chart.js v4.0.0 */\n!function(){console.log('test');}();"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        cache_file = tmppath / "chart.umd.min.js"
        cache_file.write_text(dummy_js, encoding="utf-8")

        # Monkeypatch CHARTJS_CACHE_PATH to point to our temp cache
        with patch("token_report.CHARTJS_CACHE_PATH", cache_file):
            # Also monkeypatch urllib.request.urlopen to raise if called
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.side_effect = RuntimeError("Network call should not happen!")

                result = get_chartjs_source()

                # Verify we got the cache contents
                assert result == dummy_js
                # Verify urlopen was not called
                mock_urlopen.assert_not_called()


def test_get_chartjs_source_caches_on_miss() -> None:
    """When cache is missing, download is stored and returned."""
    dummy_js = "/*! Chart.js v4.0.0 */\n!function(){console.log('test');}();"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        cache_dir = tmppath / "cache"
        cache_file = cache_dir / "chart.umd.min.js"

        # Mock the download response
        mock_response = MagicMock()
        mock_response.read.return_value = dummy_js.encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None

        with patch("token_report.CHARTJS_CACHE_PATH", cache_file):
            with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
                result = get_chartjs_source()

                # Verify we got the source
                assert result == dummy_js
                # Verify urlopen was called
                mock_urlopen.assert_called_once()
                # Verify cache was created
                assert cache_file.exists()
                assert cache_file.read_text(encoding="utf-8") == dummy_js


def test_get_chartjs_source_returns_nonempty() -> None:
    """Returned source is non-empty and starts with valid JS preamble."""
    dummy_js = "/*! Chart.js */\nvar Chart = {};"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        cache_file = tmppath / "chart.umd.min.js"
        cache_file.write_text(dummy_js, encoding="utf-8")

        with patch("token_report.CHARTJS_CACHE_PATH", cache_file):
            with patch("urllib.request.urlopen"):
                result = get_chartjs_source()

                # Verify non-empty
                assert len(result) > 0
                # Verify starts with valid preamble
                stripped = result.strip()
                valid_starts = ("/*", "//", "!", "(")
                assert any(stripped.startswith(start) for start in valid_starts)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

AGENT_TOTALS = {
    "designer": {
        "input_tokens": 1234567,
        "output_tokens": 200,
        "cache_read_tokens": 10000,
        "cache_write_tokens": 500,
        "cost_usd": 0.001234,
    },
    "architect": {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_tokens": 300,
        "cache_write_tokens": 0,
        "cost_usd": 0.000050,
    },
}

GRAND_TOTAL = {
    "input_tokens": 1234667,
    "output_tokens": 250,
    "cache_read_tokens": 10300,
    "cache_write_tokens": 500,
    "cost_usd": 0.001284,
}

MINUTE_BUCKETS = [
    {
        "minute": "2026-03-30T12:55:00Z",
        "agent": "architect",
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_tokens": 300,
        "cache_write_tokens": 0,
        "cost_usd": 0.000050,
    },
    {
        "minute": "2026-03-30T12:55:00Z",
        "agent": "designer",
        "input_tokens": 1234567,
        "output_tokens": 200,
        "cache_read_tokens": 10000,
        "cache_write_tokens": 500,
        "cost_usd": 0.001234,
    },
]

DUMMY_CHARTJS = "/*! Chart.js v4.0.0 */\nvar Chart = function(){};"


# ---------------------------------------------------------------------------
# render_summary_table tests
# ---------------------------------------------------------------------------


def test_summary_table_contains_agent_names() -> None:
    """Summary table rows include agent names."""
    html = render_summary_table(AGENT_TOTALS, GRAND_TOTAL)
    assert "designer" in html
    assert "architect" in html


def test_summary_table_thousands_separator() -> None:
    """Token counts use thousands separators (e.g. 1,234,567)."""
    html = render_summary_table(AGENT_TOTALS, GRAND_TOTAL)
    assert "1,234,567" in html


def test_summary_table_cost_six_decimal_places() -> None:
    """Cost values are formatted to 6 decimal places."""
    html = render_summary_table(AGENT_TOTALS, GRAND_TOTAL)
    assert "0.001234" in html


def test_summary_table_total_row() -> None:
    """Summary table contains a Total row."""
    html = render_summary_table(AGENT_TOTALS, GRAND_TOTAL)
    assert "Total" in html


def test_summary_table_header_columns() -> None:
    """Summary table header contains the required column names."""
    html = render_summary_table(AGENT_TOTALS, GRAND_TOTAL)
    assert "Agent" in html
    assert "Input Tokens" in html
    assert "Output Tokens" in html
    assert "Cache Read Tokens" in html
    assert "Cache Write Tokens" in html
    assert "Total Cost (USD)" in html


def test_summary_table_is_html_table() -> None:
    """Returned string is an HTML <table> element."""
    html = render_summary_table(AGENT_TOTALS, GRAND_TOTAL)
    assert html.strip().startswith("<table>")
    assert "</table>" in html


# ---------------------------------------------------------------------------
# generate_html tests
# ---------------------------------------------------------------------------


def test_generate_html_contains_chartjs_bundle() -> None:
    """HTML output embeds the Chart.js bundle inside a <script> tag."""
    html = generate_html(MINUTE_BUCKETS, AGENT_TOTALS, GRAND_TOTAL, DUMMY_CHARTJS)
    assert DUMMY_CHARTJS in html
    assert "<script>" in html


def test_generate_html_contains_table() -> None:
    """HTML output contains a <table> element."""
    html = generate_html(MINUTE_BUCKETS, AGENT_TOTALS, GRAND_TOTAL, DUMMY_CHARTJS)
    assert "<table>" in html


def test_generate_html_contains_canvas() -> None:
    """HTML output contains a <canvas> element for the chart."""
    html = generate_html(MINUTE_BUCKETS, AGENT_TOTALS, GRAND_TOTAL, DUMMY_CHARTJS)
    assert "<canvas" in html


def test_generate_html_embedded_json_token_dataset_labels() -> None:
    """Embedded JSON contains correct dataset labels for token-count view."""
    html = generate_html(MINUTE_BUCKETS, AGENT_TOTALS, GRAND_TOTAL, DUMMY_CHARTJS)
    # The JSON embedded in the script should contain all minute buckets
    # Check that agent names and token type labels appear
    assert "designer \u00b7 input_tokens" in html or "designer · input_tokens" in html
    assert "architect \u00b7 output_tokens" in html or "architect · output_tokens" in html


def test_generate_html_embedded_json_cost_dataset_labels() -> None:
    """Embedded JSON contains correct dataset labels for cost view."""
    html = generate_html(MINUTE_BUCKETS, AGENT_TOTALS, GRAND_TOTAL, DUMMY_CHARTJS)
    assert "designer \u00b7 cost_usd" in html or "designer · cost_usd" in html
    assert "architect \u00b7 cost_usd" in html or "architect · cost_usd" in html


def test_generate_html_embedded_json_literal() -> None:
    """Embedded JSON literal in <script> block contains all minute bucket data."""
    html = generate_html(MINUTE_BUCKETS, AGENT_TOTALS, GRAND_TOTAL, DUMMY_CHARTJS)
    # Verify the JSON data is embedded (check a value that's distinctive)
    assert "2026-03-30T12:55:00Z" in html


def test_generate_html_controls() -> None:
    """HTML contains toggle button, two datetime-local inputs, and Reset button."""
    html = generate_html(MINUTE_BUCKETS, AGENT_TOTALS, GRAND_TOTAL, DUMMY_CHARTJS)
    assert 'type="datetime-local"' in html
    # There should be two datetime-local inputs
    assert html.count('type="datetime-local"') == 2
    assert "Reset" in html
    # Toggle button is present
    assert "Switch to Cost USD" in html or "Switch to Token Counts" in html


def test_generate_html_chart_js_initialization() -> None:
    """HTML contains Chart.js initialization code (new Chart(...))."""
    html = generate_html(MINUTE_BUCKETS, AGENT_TOTALS, GRAND_TOTAL, DUMMY_CHARTJS)
    assert "new Chart(" in html
