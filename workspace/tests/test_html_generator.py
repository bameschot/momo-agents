"""Tests for build_html() — page skeleton, summary table, and Chart.js embedding."""

from __future__ import annotations

import json

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


def test_build_html_embeds_chartjs_src(sample_agg):
    """chartjs_src must be embedded verbatim inside a <script> tag."""
    sentinel = "UNIQUE_SENTINEL_STRING_XYZ_987"
    html = build_html(sample_agg, sentinel)
    assert sentinel in html


def test_build_html_has_canvas(sample_agg):
    """HTML must contain <canvas id="tokenChart"> inside #chart-container."""
    html = build_html(sample_agg, "")
    assert '<canvas id="tokenChart">' in html
    assert 'id="chart-container"' in html


def test_build_html_has_interactive_controls(sample_agg):
    """HTML must contain the toggle button, date pickers, and reset button."""
    html = build_html(sample_agg, "")
    assert 'id="toggleBtn"' in html
    assert "Switch to Cost USD" in html
    assert 'id="fromPicker"' in html
    assert 'type="datetime-local"' in html
    assert 'id="toPicker"' in html
    assert 'id="resetBtn"' in html


def test_build_html_contains_raw_data_variable(sample_agg):
    """HTML must contain the JS variable declaration const RAW_DATA =."""
    html = build_html(sample_agg, "")
    assert "const RAW_DATA =" in html


def test_build_html_raw_data_is_valid_json(sample_agg):
    """The embedded RAW_DATA JSON must be parseable and have the required keys."""
    html = build_html(sample_agg, "")
    # Extract the JSON between "const RAW_DATA = " and the first ";\n"
    marker = "const RAW_DATA = "
    start = html.index(marker) + len(marker)
    end = html.index(";\n", start)
    raw_json = html[start:end]
    data = json.loads(raw_json)
    assert "labels" in data
    assert "token_series" in data
    assert "cost_series" in data


def test_build_html_raw_data_token_series_coverage(sample_agg):
    """A token_series entry must exist for every (agent, token_type) combination."""
    html = build_html(sample_agg, "")
    marker = "const RAW_DATA = "
    start = html.index(marker) + len(marker)
    end = html.index(";\n", start)
    data = json.loads(html[start:end])
    series_labels = {s["label"] for s in data["token_series"]}
    token_types = ["input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"]
    for agent in sample_agg["agent_totals"]:
        for token_type in token_types:
            expected_label = f"{agent} \u00b7 {token_type}"
            assert expected_label in series_labels, f"Missing token series: {expected_label}"


def test_build_html_raw_data_cost_series_coverage(sample_agg):
    """A cost_series entry must exist for every agent."""
    html = build_html(sample_agg, "")
    marker = "const RAW_DATA = "
    start = html.index(marker) + len(marker)
    end = html.index(";\n", start)
    data = json.loads(html[start:end])
    cost_labels = {s["label"] for s in data["cost_series"]}
    for agent in sample_agg["agent_totals"]:
        expected_label = f"{agent} \u00b7 cost_usd"
        assert expected_label in cost_labels, f"Missing cost series: {expected_label}"


def test_build_html_raw_data_zero_fill_for_missing_minutes(sample_agg):
    """For an agent with no records in a given minute bucket, the data point must be 0."""
    # sample data: "ba" has no record at 12:01, "designer" has no record at 12:02
    html = build_html(sample_agg, "")
    marker = "const RAW_DATA = "
    start = html.index(marker) + len(marker)
    end = html.index(";\n", start)
    data = json.loads(html[start:end])
    labels = data["labels"]
    # Find the index of "2026-03-30T12:01:00Z" (designer-only minute)
    if "2026-03-30T12:01:00Z" in labels:
        idx_12_01 = labels.index("2026-03-30T12:01:00Z")
        for series in data["token_series"]:
            if series["label"].startswith("ba \u00b7"):
                assert series["data"][idx_12_01] == 0, (
                    f"Expected 0 for 'ba' at 12:01, got {series['data'][idx_12_01]}"
                )
    # Find the index of "2026-03-30T12:02:00Z" (ba-only minute)
    if "2026-03-30T12:02:00Z" in labels:
        idx_12_02 = labels.index("2026-03-30T12:02:00Z")
        for series in data["token_series"]:
            if series["label"].startswith("designer \u00b7"):
                assert series["data"][idx_12_02] == 0, (
                    f"Expected 0 for 'designer' at 12:02, got {series['data'][idx_12_02]}"
                )


def test_build_html_chart_initialisation_script(sample_agg):
    """HTML must contain Chart.js initialisation assigning to window.chart."""
    html = build_html(sample_agg, "")
    assert "window.chart" in html
    assert "new Chart(" in html
    assert "Token Usage Over Time" in html


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
