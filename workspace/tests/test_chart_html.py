"""Tests for the render_chart_html function in token_report."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from token_report import render_chart_html  # noqa: E402

FAKE_CHARTJS = "/* fake chartjs */"

SAMPLE_BUCKETS = [
    {
        "minute": "2026-03-31T10:00:00Z",
        "agent": "designer",
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_tokens": 10,
        "cache_write_tokens": 5,
        "cost_usd": 0.001234,
    },
    {
        "minute": "2026-03-31T10:01:00Z",
        "agent": "designer",
        "input_tokens": 200,
        "output_tokens": 80,
        "cache_read_tokens": 20,
        "cache_write_tokens": 8,
        "cost_usd": 0.002345,
    },
    {
        "minute": "2026-03-31T10:00:00Z",
        "agent": "coder",
        "input_tokens": 150,
        "output_tokens": 60,
        "cache_read_tokens": 15,
        "cache_write_tokens": 6,
        "cost_usd": 0.001500,
    },
    {
        "minute": "2026-03-31T10:01:00Z",
        "agent": "coder",
        "input_tokens": 300,
        "output_tokens": 90,
        "cache_read_tokens": 30,
        "cache_write_tokens": 9,
        "cost_usd": 0.003000,
    },
]


class TestDataEmbedding:
    """Tests that bucket data is embedded correctly in the HTML output."""

    def test_minute_strings_appear_in_script_block(self):
        """Assert that minute strings from buckets appear in the script block."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert "2026-03-31T10:00:00Z" in html
        assert "2026-03-31T10:01:00Z" in html

    def test_buckets_serialised_as_json_literal(self):
        """Assert that the raw buckets JSON literal is present in the HTML."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        # json.dumps will produce values like "designer" in the JSON
        buckets_json = json.dumps(SAMPLE_BUCKETS, default=str)
        assert buckets_json in html

    def test_raw_buckets_variable_present(self):
        """Assert that the RAW_BUCKETS variable is declared in the script."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert "RAW_BUCKETS" in html


class TestSeriesLabels:
    """Tests that dataset labels are correctly included in the HTML."""

    def test_token_count_labels_for_agent_token_type_combinations(self):
        """Assert HTML contains dataset labels for each (agent, token_type) pair."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        token_types = [
            "input_tokens",
            "output_tokens",
            "cache_read_tokens",
            "cache_write_tokens",
        ]
        for agent in ["designer", "coder"]:
            for tt in token_types:
                expected_label = f"{agent} \u00b7 {tt}"
                assert expected_label in html, (
                    f"Expected label '{expected_label}' not found in HTML"
                )

    def test_cost_usd_labels_for_each_agent(self):
        """Assert HTML contains cost_usd labels for each agent."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        for agent in ["designer", "coder"]:
            expected_label = f"{agent} \u00b7 cost_usd"
            assert expected_label in html, (
                f"Expected cost label '{expected_label}' not found in HTML"
            )


class TestControlsPresent:
    """Tests that all required UI controls are present in the HTML."""

    def test_toggle_button_present(self):
        """Assert a toggle button element is present."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert "<button" in html
        # The toggle button should reference toggle functionality
        assert "toggleView" in html or "toggleBtn" in html

    def test_two_datetime_local_inputs_present(self):
        """Assert two datetime-local inputs are present for date-range filtering."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert html.count('type="datetime-local"') == 2

    def test_reset_button_present(self):
        """Assert a Reset button element is present."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert "Reset" in html
        assert "resetFilter" in html or "resetBtn" in html

    def test_from_picker_present(self):
        """Assert a From date picker is present."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert "fromPicker" in html or "From" in html

    def test_to_picker_present(self):
        """Assert a To date picker is present."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert "toPicker" in html or "To:" in html


class TestCanvasPresent:
    """Tests that the canvas element is correctly present."""

    def test_canvas_with_token_chart_id_present(self):
        """Assert a canvas element with id='tokenChart' is present."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert '<canvas id="tokenChart"' in html


class TestChartjsInjection:
    """Tests that the Chart.js source is injected into the HTML."""

    def test_chartjs_src_appears_in_html(self):
        """Assert the chartjs_src string appears verbatim in the returned HTML."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert FAKE_CHARTJS in html

    def test_chartjs_wrapped_in_script_tag(self):
        """Assert chartjs_src is wrapped in a <script> tag."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert f"<script>{FAKE_CHARTJS}</script>" in html

    def test_different_chartjs_src(self):
        """Assert a different chartjs_src value is also embedded correctly."""
        custom_src = "var Chart = function() {};"
        html = render_chart_html(SAMPLE_BUCKETS, custom_src)
        assert custom_src in html


class TestChartBehaviour:
    """Tests that Chart.js initialisation logic is present."""

    def test_domcontentloaded_listener_present(self):
        """Assert chart is initialised on DOMContentLoaded."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert "DOMContentLoaded" in html

    def test_chart_title_token_usage_present(self):
        """Assert the 'Token Usage Over Time' title is referenced in JS."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert "Token Usage Over Time" in html

    def test_chart_title_cost_over_time_present(self):
        """Assert the 'Cost Over Time' title is referenced in JS."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert "Cost Over Time" in html

    def test_y_axis_token_count_label_present(self):
        """Assert 'Token Count' y-axis label is in the JS."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert "Token Count" in html

    def test_y_axis_cost_usd_label_present(self):
        """Assert 'Cost (USD)' y-axis label is in the JS."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert "Cost (USD)" in html

    def test_chart_destroy_and_recreate_on_toggle(self):
        """Assert chart.destroy() is called to handle view switching."""
        html = render_chart_html(SAMPLE_BUCKETS, FAKE_CHARTJS)
        assert "chart.destroy()" in html

    def test_empty_buckets_produces_valid_html(self):
        """Assert empty bucket list still produces valid HTML structure."""
        html = render_chart_html([], FAKE_CHARTJS)
        assert '<canvas id="tokenChart"' in html
        assert FAKE_CHARTJS in html
        assert "RAW_BUCKETS" in html
