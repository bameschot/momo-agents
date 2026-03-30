"""Tests for build_html() — page skeleton and summary table."""

from __future__ import annotations

import pytest

from token_report import aggregate, build_html


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_agg(sample_records):
    """Return aggregated data from the shared sample records."""
    return aggregate(sample_records)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_build_html_returns_valid_html5(sample_agg):
    """build_html() must return a string starting with <!DOCTYPE html>."""
    html = build_html(sample_agg, "")
    assert isinstance(html, str)
    assert html.startswith("<!DOCTYPE html>")


def test_build_html_has_charset_and_title(sample_agg):
    """<head> must contain charset meta tag and a title."""
    html = build_html(sample_agg, "")
    assert '<meta charset="utf-8">' in html
    assert "<title>" in html
    assert "Token Usage Report" in html


def test_build_html_contains_chart_container(sample_agg):
    """HTML must include a <div id="chart-container"> placeholder."""
    html = build_html(sample_agg, "")
    assert 'id="chart-container"' in html


def test_build_html_table_has_six_columns(sample_agg):
    """The summary table must have six header columns."""
    html = build_html(sample_agg, "")
    assert "Agent" in html
    assert "Input Tokens" in html
    assert "Output Tokens" in html
    assert "Cache Read Tokens" in html
    assert "Cache Write Tokens" in html
    assert "Total Cost (USD)" in html


def test_build_html_one_row_per_agent(sample_agg):
    """There should be one <tr> per agent in the table body."""
    html = build_html(sample_agg, "")
    # sample data has two agents: "ba" and "designer"
    agent_names = list(sample_agg["agent_totals"].keys())
    assert len(agent_names) == 2
    for agent in agent_names:
        assert f"<td>{agent}</td>" in html


def test_build_html_grand_total_row(sample_agg):
    """The HTML must contain a Grand Total row."""
    html = build_html(sample_agg, "")
    assert "Grand Total" in html


def test_build_html_thousands_separators(sample_records):
    """Token counts must use thousands separators."""
    # Use a record with a value >= 1000 to verify formatting
    records = [
        {
            "ts": "2026-03-30T12:00:00Z",
            "agent": "agent-a",
            "input_tokens": 1234,
            "output_tokens": 5678,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "cost_usd": 0.001234,
        }
    ]
    agg = aggregate(records)
    html = build_html(agg, "")
    assert "1,234" in html
    assert "5,678" in html


def test_build_html_cost_six_decimal_places(sample_records):
    """Cost values must be formatted to exactly 6 decimal places."""
    records = [
        {
            "ts": "2026-03-30T12:00:00Z",
            "agent": "agent-a",
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "cost_usd": 0.001234,
        }
    ]
    agg = aggregate(records)
    html = build_html(agg, "")
    assert "0.001234" in html


def test_build_html_agents_in_alphabetical_order(sample_agg):
    """Agents must appear in alphabetical order in the table."""
    html = build_html(sample_agg, "")
    # "ba" should appear before "designer"
    ba_pos = html.index("<td>ba</td>")
    designer_pos = html.index("<td>designer</td>")
    assert ba_pos < designer_pos


def test_build_html_chartjs_src_not_used(sample_agg):
    """chartjs_src is accepted but not embedded in the page yet."""
    sentinel = "UNIQUE_SENTINEL_STRING_XYZ_987"
    html = build_html(sample_agg, sentinel)
    assert sentinel not in html


def test_build_html_empty_aggregation():
    """build_html() handles an empty aggregation without crashing."""
    empty_agg = {
        "buckets": [],
        "agent_totals": {},
        "grand_total": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "cost_usd": 0.0,
        },
    }
    html = build_html(empty_agg, "")
    assert "<!DOCTYPE html>" in html
    assert "Grand Total" in html
