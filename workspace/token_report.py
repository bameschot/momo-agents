"""
token_report.py — Token Usage Report Generator

Reads per-agent token usage logs from .sentinels/tokens/*.jsonl,
aggregates the data by minute bucket, and produces a self-contained
single-page HTML report with an inline Chart.js bundle.

Usage:
    python token_report.py [--tokens-dir <path>]

Output:
    ./token-report_YYYY-MM-DD_HH-MM-SS.html  (written to CWD)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHARTJS_URL = "https://cdn.jsdelivr.net/npm/chart.js/dist/chart.umd.min.js"
CHARTJS_CACHE_PATH = Path(__file__).parent / ".chartjs_cache" / "chart.umd.min.js"

TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate a token usage HTML report from JSONL log files."
    )
    parser.add_argument(
        "--tokens-dir",
        default=".sentinels/tokens",
        help="Path to directory containing *.jsonl agent token log files "
        "(default: .sentinels/tokens relative to CWD)",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Data Loader
# ---------------------------------------------------------------------------


def load_records(tokens_dir: Path) -> list[dict]:
    """Walk tokens_dir and parse every *.jsonl file into a list of records.

    Each record is a dict with keys:
        ts, agent, input_tokens, output_tokens,
        cache_read_tokens, cache_write_tokens, cost_usd

    Blank lines and lines that fail JSON parsing are skipped with a warning.
    The agent name is derived from the filename stem.
    """
    records = []
    jsonl_files = sorted(tokens_dir.glob("*.jsonl"))

    for jsonl_file in jsonl_files:
        agent_name = jsonl_file.stem

        with open(jsonl_file, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.rstrip("\n\r")

                # Skip blank lines
                if not line.strip():
                    continue

                # Parse JSON line
                try:
                    record = json.loads(line)
                    record["agent"] = agent_name
                    records.append(record)
                except json.JSONDecodeError as e:
                    print(
                        f"Warning: {jsonl_file}:{line_num}: Failed to parse JSON: {e}",
                        file=sys.stderr,
                    )
                    continue

    return records


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


def aggregate_by_minute(records: list[dict]) -> list[dict]:
    """Group records by (agent, minute bucket) and sum token/cost fields.

    The minute bucket is the ISO-8601 timestamp truncated to the minute,
    e.g. '2026-03-30T12:55:00Z'.

    Returns a list of aggregated dicts sorted by (minute, agent).
    """
    buckets: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "cost_usd": 0.0,
        }
    )

    for record in records:
        # Truncate timestamp to minute
        ts = record["ts"]
        dt = datetime.fromisoformat(ts.rstrip("Z"))
        dt = dt.replace(second=0, microsecond=0)
        minute_bucket = dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

        agent = record["agent"]
        key = (minute_bucket, agent)

        # Sum the numeric fields
        for field in TOKEN_FIELDS:
            buckets[key][field] += record.get(field, 0)
        buckets[key]["cost_usd"] += record.get("cost_usd", 0.0)

    # Convert to list and sort by (minute, agent)
    result = []
    for (minute, agent), totals in sorted(buckets.items()):
        result.append(
            {
                "minute": minute,
                "agent": agent,
                **totals,
            }
        )

    return result


def compute_agent_totals(records: list[dict]) -> dict[str, dict]:
    """Compute per-agent totals across all time.

    Returns a dict keyed by agent name, each value being a dict with:
        input_tokens, output_tokens, cache_read_tokens,
        cache_write_tokens, cost_usd
    """
    totals: dict[str, dict] = defaultdict(
        lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "cost_usd": 0.0,
        }
    )

    for record in records:
        agent = record["agent"]
        for field in TOKEN_FIELDS:
            totals[agent][field] += record.get(field, 0)
        totals[agent]["cost_usd"] += record.get("cost_usd", 0.0)

    return dict(totals)


def compute_grand_total(agent_totals: dict[str, dict]) -> dict:
    """Sum all agents into a single grand-total dict."""
    grand_total = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "cost_usd": 0.0,
    }

    for agent_dict in agent_totals.values():
        for field in TOKEN_FIELDS:
            grand_total[field] += agent_dict.get(field, 0)
        grand_total["cost_usd"] += agent_dict.get("cost_usd", 0.0)

    return grand_total


# ---------------------------------------------------------------------------
# Chart.js Bundle
# ---------------------------------------------------------------------------


def get_chartjs_source() -> str:
    """Return the Chart.js UMD source, using a local cache when available.

    Downloads from CHARTJS_URL on first run and caches to CHARTJS_CACHE_PATH.
    """
    # Check if cache exists
    if CHARTJS_CACHE_PATH.exists():
        return CHARTJS_CACHE_PATH.read_text(encoding="utf-8")

    # Cache miss: download from CDN
    try:
        with urllib.request.urlopen(CHARTJS_URL, timeout=15) as response:
            chartjs_source = response.read().decode("utf-8")
    except Exception as e:
        print(f"Error downloading Chart.js from {CHARTJS_URL}: {e}", file=sys.stderr)
        raise

    # Ensure returned string is valid (non-empty and looks like JS)
    if not chartjs_source or not (
        chartjs_source.strip().startswith("/*")
        or chartjs_source.strip().startswith("//")
        or chartjs_source.strip().startswith("!")
        or chartjs_source.strip().startswith("(")
    ):
        raise ValueError(
            f"Invalid Chart.js source: expected to start with JS comment or UMD preamble, "
            f"got: {chartjs_source[:100]}"
        )

    # Create cache directory and write cache
    CHARTJS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHARTJS_CACHE_PATH.write_text(chartjs_source, encoding="utf-8")

    return chartjs_source


# ---------------------------------------------------------------------------
# HTML / Chart Generator
# ---------------------------------------------------------------------------


def render_summary_table(agent_totals: dict[str, dict], grand_total: dict) -> str:
    """Return an HTML <table> string for the per-agent summary.

    Columns: Agent | Input Tokens | Output Tokens | Cache Read Tokens |
             Cache Write Tokens | Total Cost (USD)

    Numbers use thousands separators; cost is formatted to 6 decimal places.
    Last row is the grand-total row.
    """
    rows = []
    for agent in sorted(agent_totals.keys()):
        t = agent_totals[agent]
        rows.append(
            f"<tr>"
            f"<td>{agent}</td>"
            f"<td>{t['input_tokens']:,}</td>"
            f"<td>{t['output_tokens']:,}</td>"
            f"<td>{t['cache_read_tokens']:,}</td>"
            f"<td>{t['cache_write_tokens']:,}</td>"
            f"<td>{t['cost_usd']:.6f}</td>"
            f"</tr>"
        )

    gt = grand_total
    rows.append(
        f"<tr class='total-row'>"
        f"<td><strong>Total</strong></td>"
        f"<td><strong>{gt['input_tokens']:,}</strong></td>"
        f"<td><strong>{gt['output_tokens']:,}</strong></td>"
        f"<td><strong>{gt['cache_read_tokens']:,}</strong></td>"
        f"<td><strong>{gt['cache_write_tokens']:,}</strong></td>"
        f"<td><strong>{gt['cost_usd']:.6f}</strong></td>"
        f"</tr>"
    )

    rows_html = "\n".join(rows)
    return (
        "<table>\n"
        "<thead><tr>"
        "<th>Agent</th>"
        "<th>Input Tokens</th>"
        "<th>Output Tokens</th>"
        "<th>Cache Read Tokens</th>"
        "<th>Cache Write Tokens</th>"
        "<th>Total Cost (USD)</th>"
        "</tr></thead>\n"
        f"<tbody>\n{rows_html}\n</tbody>\n"
        "</table>"
    )


def _build_chart_data(minute_buckets: list[dict]) -> dict:
    """Pre-compute chart datasets from minute_buckets for embedding as JSON.

    Returns a dict with:
        buckets       – the raw minute_buckets list
        tokenDatasets – list of dataset dicts (label, data) for token-count view
        costDatasets  – list of dataset dicts (label, data) for cost view
        allMinutes    – sorted list of all unique minute strings
    """
    agents = sorted({b["agent"] for b in minute_buckets})
    all_minutes = sorted({b["minute"] for b in minute_buckets})

    colors = [
        "#4e79a7",
        "#f28e2b",
        "#e15759",
        "#76b7b2",
        "#59a14f",
        "#edc948",
        "#b07aa1",
        "#ff9da7",
        "#9c755f",
        "#bab0ac",
        "#499894",
        "#86bcb6",
    ]

    def sum_field(agent: str, minute: str, field: str) -> float:
        return sum(
            b.get(field, 0) for b in minute_buckets if b["agent"] == agent and b["minute"] == minute
        )

    token_datasets = []
    color_idx = 0
    for agent in agents:
        for tt in TOKEN_FIELDS:
            data = [sum_field(agent, m, tt) for m in all_minutes]
            token_datasets.append(
                {
                    "label": f"{agent} \u00b7 {tt}",
                    "data": data,
                    "borderColor": colors[color_idx % len(colors)],
                    "backgroundColor": colors[color_idx % len(colors)],
                    "fill": False,
                    "tension": 0.1,
                }
            )
            color_idx += 1

    cost_datasets = []
    for i, agent in enumerate(agents):
        data = [sum_field(agent, m, "cost_usd") for m in all_minutes]
        cost_datasets.append(
            {
                "label": f"{agent} \u00b7 cost_usd",
                "data": data,
                "borderColor": colors[i % len(colors)],
                "backgroundColor": colors[i % len(colors)],
                "fill": False,
                "tension": 0.1,
            }
        )

    return {
        "buckets": minute_buckets,
        "tokenDatasets": token_datasets,
        "costDatasets": cost_datasets,
        "allMinutes": all_minutes,
    }


def render_html(
    summary_table_html: str,
    minute_buckets: list[dict],
    chartjs_source: str,
) -> str:
    """Render and return the complete self-contained HTML report string.

    Embeds:
    - summary_table_html inside the page body
    - minute_buckets as a JSON literal in a <script> block
    - chartjs_source inside a <script> tag
    - Client-side JS for toggle, date filtering, and Chart.js initialisation
    """
    chart_data = _build_chart_data(minute_buckets)
    data_json = json.dumps(chart_data, ensure_ascii=False)

    client_js = r"""
    const chartData = DATA_PLACEHOLDER;
    const allBuckets = chartData.buckets;

    function getMinutes(buckets) {
        const seen = new Set();
        for (const b of buckets) seen.add(b.minute);
        return Array.from(seen).sort();
    }

    let showCost = false;
    let chartInstance = null;

    function filterBucketsByDate() {
        const fromVal = document.getElementById('from-date').value;
        const toVal = document.getElementById('to-date').value;
        if (!fromVal && !toVal) return allBuckets;
        return allBuckets.filter(function(b) {
            const m = b.minute;
            if (fromVal) {
                const fromStr = fromVal.slice(0, 16) + ':00Z';
                if (m < fromStr) return false;
            }
            if (toVal) {
                const toStr = toVal.slice(0, 16) + ':00Z';
                if (m > toStr) return false;
            }
            return true;
        });
    }

    function rebuildDataArrays(templateDatasets, filteredBuckets, filteredMinutes, costMode) {
        return templateDatasets.map(function(ds) {
            var parts = ds.label.split(' \u00b7 ');
            var agent = parts[0];
            var field = parts[1];
            var data = filteredMinutes.map(function(m) {
                var val = 0;
                for (var i = 0; i < filteredBuckets.length; i++) {
                    var b = filteredBuckets[i];
                    if (b.minute === m && b.agent === agent) val += b[field];
                }
                return val;
            });
            return Object.assign({}, ds, { data: data });
        });
    }

    function renderChart() {
        const ctx = document.getElementById('tokenChart').getContext('2d');
        if (chartInstance) { chartInstance.destroy(); chartInstance = null; }

        const filteredBuckets = filterBucketsByDate();
        const filteredMinutes = getMinutes(filteredBuckets);

        const templateDatasets = showCost ? chartData.costDatasets : chartData.tokenDatasets;
        const datasets = rebuildDataArrays(
            templateDatasets, filteredBuckets, filteredMinutes, showCost
        );

        const yLabel = showCost ? 'Cost (USD)' : 'Token Count';
        const chartTitle = showCost ? 'Token Cost Over Time' : 'Token Usage Over Time';

        chartInstance = new Chart(ctx, {
            type: 'line',
            data: { labels: filteredMinutes, datasets: datasets },
            options: {
                responsive: true,
                plugins: {
                    title: { display: true, text: chartTitle },
                    legend: { position: 'top' }
                },
                scales: {
                    y: { title: { display: true, text: yLabel } },
                    x: { title: { display: true, text: 'Time (UTC)' } }
                }
            }
        });
    }

    document.getElementById('toggle-btn').addEventListener('click', function() {
        showCost = !showCost;
        this.textContent = showCost ? 'Switch to Token Counts' : 'Switch to Cost USD';
        renderChart();
    });

    document.getElementById('from-date').addEventListener('change', renderChart);
    document.getElementById('to-date').addEventListener('change', renderChart);
    document.getElementById('reset-btn').addEventListener('click', function() {
        document.getElementById('from-date').value = '';
        document.getElementById('to-date').value = '';
        renderChart();
    });

    renderChart();
    """

    client_js = client_js.replace("DATA_PLACEHOLDER", data_json)

    html = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        "<title>Token Usage Report</title>\n"
        "<style>\n"
        "body { font-family: sans-serif; margin: 2em; }\n"
        "table { border-collapse: collapse; width: 100%; margin-bottom: 2em; }\n"
        "th, td { border: 1px solid #ccc; padding: 0.5em 1em; text-align: right; }\n"
        "th:first-child, td:first-child { text-align: left; }\n"
        "th { background: #f0f0f0; }\n"
        ".total-row td { background: #f8f8f8; }\n"
        ".controls { margin-bottom: 1.5em; display: flex; gap: 1em;"
        " align-items: center; flex-wrap: wrap; }\n"
        ".chart-container { position: relative; width: 100%; max-height: 500px; }\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        "<h1>Token Usage Report</h1>\n"
        "<h2>Summary</h2>\n" + summary_table_html + "\n"
        "<h2>Chart</h2>\n"
        '<div class="controls">\n'
        '  <button id="toggle-btn">Switch to Cost USD</button>\n'
        '  <label>From: <input type="datetime-local" id="from-date"></label>\n'
        '  <label>To: <input type="datetime-local" id="to-date"></label>\n'
        '  <button id="reset-btn">Reset</button>\n'
        "</div>\n"
        '<div class="chart-container">\n'
        '  <canvas id="tokenChart"></canvas>\n'
        "</div>\n"
        "<script>\n" + chartjs_source + "\n</script>\n"
        "<script>\n" + client_js + "\n</script>\n"
        "</body>\n"
        "</html>\n"
    )

    return html


def generate_html(
    minute_buckets: list[dict],
    agent_totals: dict[str, dict],
    grand_total: dict,
    chartjs_source: str,
) -> str:
    """Convenience wrapper: render summary table then full HTML.

    Parameters match what tests call directly.
    """
    summary_table_html = render_summary_table(agent_totals, grand_total)
    return render_html(summary_table_html, minute_buckets, chartjs_source)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Main entry point. Returns exit code (0 = success, 1 = error)."""
    args = parse_args(argv)
    tokens_dir = Path(args.tokens_dir)

    # Validate tokens directory
    if not tokens_dir.is_dir():
        print(f"Error: tokens directory not found: {tokens_dir}", file=sys.stderr)
        return 1

    jsonl_files = list(tokens_dir.glob("*.jsonl"))
    if not jsonl_files:
        print(f"Error: no *.jsonl files found in {tokens_dir}", file=sys.stderr)
        return 1

    # Load, aggregate, render
    records = load_records(tokens_dir)
    minute_buckets = aggregate_by_minute(records)
    agent_totals = compute_agent_totals(records)
    grand_total = compute_grand_total(agent_totals)

    chartjs_source = get_chartjs_source()
    summary_table_html = render_summary_table(agent_totals, grand_total)
    html = render_html(summary_table_html, minute_buckets, chartjs_source)

    # Write output file
    now = datetime.now(tz=timezone.utc)
    output_filename = now.strftime("token-report_%Y-%m-%d_%H-%M-%S.html")
    output_path = Path.cwd() / output_filename
    output_path.write_text(html, encoding="utf-8")

    print(str(output_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
