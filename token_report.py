"""
token_report.py — Token Usage Report Generator

Reads per-agent token usage logs from a directory of *.jsonl files,
aggregates the data by minute bucket, and produces a self-contained
single-page HTML report with an interactive Chart.js line chart.

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
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate an HTML token-usage report from agent JSONL logs.",
    )
    parser.add_argument(
        "--tokens-dir",
        default=".sentinels/tokens",
        metavar="PATH",
        help="Path to directory containing *.jsonl token log files "
             "(default: .sentinels/tokens relative to CWD).",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# 2. Data Loader
# ---------------------------------------------------------------------------

def load_records(tokens_dir: Path) -> list[dict]:
    """Walk tokens_dir, parse every *.jsonl file, and return a flat list of records.

    Each record is a dict with keys:
        ts, agent, input_tokens, output_tokens,
        cache_read_tokens, cache_write_tokens, cost_usd

    Skips blank lines and lines that fail JSON parsing (warns to stderr).
    Raises SystemExit(1) if tokens_dir does not exist or contains no *.jsonl files.
    """
    # Check if directory exists
    if not tokens_dir.exists():
        print(f"Error: tokens directory not found: {tokens_dir}", file=sys.stderr)
        sys.exit(1)

    # Find all .jsonl files
    jsonl_files = sorted(tokens_dir.glob("*.jsonl"))
    if not jsonl_files:
        print(
            f"Error: no .jsonl files found in {tokens_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    records = []

    # Process each .jsonl file
    for jsonl_file in jsonl_files:
        agent_name = jsonl_file.stem
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                # Skip blank lines silently
                if not line.strip():
                    continue

                # Try to parse as JSON
                try:
                    record = json.loads(line)
                    # Inject agent name
                    record["agent"] = agent_name
                    records.append(record)
                except (json.JSONDecodeError, ValueError):
                    print(
                        f"Warning: skipping unparseable line in {jsonl_file.name}: {line.rstrip()}",
                        file=sys.stderr,
                    )

    return records


# ---------------------------------------------------------------------------
# 3. Aggregator
# ---------------------------------------------------------------------------

def aggregate(records: list[dict]) -> dict:
    """Aggregate records into minute buckets and per-agent totals.

    Returns a dict:
    {
        "buckets": [
            {
                "minute": "YYYY-MM-DDTHH:MM:00Z",
                "agent":  "<name>",
                "input_tokens": int,
                "output_tokens": int,
                "cache_read_tokens": int,
                "cache_write_tokens": int,
                "cost_usd": float,
            },
            ...
        ],
        "agent_totals": {
            "<agent>": {
                "input_tokens": int,
                "output_tokens": int,
                "cache_read_tokens": int,
                "cache_write_tokens": int,
                "cost_usd": float,
            },
            ...
        },
        "grand_total": {
            "input_tokens": int,
            "output_tokens": int,
            "cache_read_tokens": int,
            "cache_write_tokens": int,
            "cost_usd": float,
        },
    }
    """
    def _zero() -> dict:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "cost_usd": 0.0,
        }

    # Accumulate per (minute, agent) bucket sums
    bucket_map: dict = defaultdict(lambda: defaultdict(_zero))
    # Accumulate per-agent totals
    agent_map: dict = defaultdict(_zero)

    numeric_keys = (
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "cost_usd",
    )

    for rec in records:
        ts: str = rec["ts"]
        agent: str = rec["agent"]
        # Derive minute bucket: YYYY-MM-DDTHH:MM:00Z
        minute = ts[:16] + ":00Z"

        bucket = bucket_map[minute][agent]
        totals = agent_map[agent]

        for key in numeric_keys:
            bucket[key] += rec.get(key, 0)
            totals[key] += rec.get(key, 0)

    # Build sorted buckets list
    buckets = []
    for minute in sorted(bucket_map.keys()):
        for agent in sorted(bucket_map[minute].keys()):
            entry = {"minute": minute, "agent": agent}
            entry.update(bucket_map[minute][agent])
            buckets.append(entry)

    # Build agent_totals dict
    agent_totals = {agent: dict(totals) for agent, totals in sorted(agent_map.items())}

    # Build grand_total
    grand_total = _zero()
    for totals in agent_map.values():
        for key in numeric_keys:
            grand_total[key] += totals[key]

    return {
        "buckets": buckets,
        "agent_totals": agent_totals,
        "grand_total": grand_total,
    }


# ---------------------------------------------------------------------------
# 4. Chart.js bundle fetcher
# ---------------------------------------------------------------------------

CHARTJS_CDN_URL = "https://cdn.jsdelivr.net/npm/chart.js/dist/chart.umd.min.js"


def fetch_chartjs(cache_dir: Path) -> str:
    """Return the Chart.js UMD bundle source as a string.

    Checks cache_dir/chart.umd.min.js first; downloads from CDN if absent.
    The downloaded file is saved to cache_dir for subsequent runs.
    """
    cache_path = cache_dir / "chart.umd.min.js"

    # If cached file exists and is non-empty, return it
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path.read_text(encoding="utf-8")

    # Create cache directory (including parents)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Download from CDN
    with urllib.request.urlopen(CHARTJS_CDN_URL) as response:
        content = response.read().decode("utf-8")

    # Save to cache
    cache_path.write_text(content, encoding="utf-8")

    return content


# ---------------------------------------------------------------------------
# 5. HTML / Chart Generator
# ---------------------------------------------------------------------------

def build_html(agg: dict, chartjs_src: str) -> str:
    """Build and return the full HTML report as a string.

    The returned string is a complete, self-contained HTML document containing:
      - A summary table (per-agent token counts + cost, plus a grand-total row)
      - A <div id="chart-container"> with a <canvas id="tokenChart">
      - Interactive controls: toggle button, date pickers, reset button
      - Embedded Chart.js bundle and chart initialisation
    """
    # Build table rows for each agent (alphabetical order)
    rows = []
    for agent, totals in sorted(agg["agent_totals"].items()):
        row = (
            f"    <tr>"
            f"<td>{agent}</td>"
            f"<td>{totals['input_tokens']:,}</td>"
            f"<td>{totals['output_tokens']:,}</td>"
            f"<td>{totals['cache_read_tokens']:,}</td>"
            f"<td>{totals['cache_write_tokens']:,}</td>"
            f"<td>{totals['cost_usd']:.6f}</td>"
            f"</tr>"
        )
        rows.append(row)

    tbody = "\n".join(rows)

    # Grand total row
    gt = agg["grand_total"]
    tfoot_row = (
        f"    <tr>"
        f"<td><strong>Grand Total</strong></td>"
        f"<td>{gt['input_tokens']:,}</td>"
        f"<td>{gt['output_tokens']:,}</td>"
        f"<td>{gt['cache_read_tokens']:,}</td>"
        f"<td>{gt['cache_write_tokens']:,}</td>"
        f"<td>{gt['cost_usd']:.6f}</td>"
        f"</tr>"
    )

    # ------------------------------------------------------------------
    # Build RAW_DATA for Chart.js
    # ------------------------------------------------------------------
    all_minutes = sorted({b["minute"] for b in agg["buckets"]})
    all_agents = sorted(agg["agent_totals"].keys())
    token_types = [
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
    ]

    # Lookup table: (minute, agent) -> bucket dict
    bucket_lookup = {(b["minute"], b["agent"]): b for b in agg["buckets"]}

    token_series = []
    for agent in all_agents:
        for token_type in token_types:
            data = [
                bucket_lookup.get((minute, agent), {}).get(token_type, 0)
                for minute in all_minutes
            ]
            token_series.append({"label": f"{agent} \u00b7 {token_type}", "data": data})

    cost_series = []
    for agent in all_agents:
        data = [
            bucket_lookup.get((minute, agent), {}).get("cost_usd", 0)
            for minute in all_minutes
        ]
        cost_series.append({"label": f"{agent} \u00b7 cost_usd", "data": data})

    raw_data = {
        "labels": all_minutes,
        "token_series": token_series,
        "cost_series": cost_series,
    }
    raw_data_json = json.dumps(raw_data)

    # ------------------------------------------------------------------
    # Chart initialisation JS
    # ------------------------------------------------------------------
    chart_init_js = """\
const RAW_DATA = """ + raw_data_json + """;

(function () {
  var ctx = document.getElementById('tokenChart').getContext('2d');
  window.chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: RAW_DATA.labels,
      datasets: RAW_DATA.token_series.map(function(s) {
        return { label: s.label, data: s.data, fill: false, tension: 0.1 };
      })
    },
    options: {
      plugins: {
        title: { display: true, text: 'Token Usage Over Time' }
      },
      scales: {
        y: { title: { display: true, text: 'Tokens' } }
      }
    }
  });

  // -----------------------------------------------------------------------
  // Interactive controls
  // -----------------------------------------------------------------------

  var currentView = 'tokens';

  function renderChart(labels, datasets) {
    window.chart.data.labels = labels;
    window.chart.data.datasets = datasets.map(function(s) {
      return { label: s.label, data: s.data, fill: false, tension: 0.1 };
    });
    window.chart.update();
  }

  function getFilteredIndices() {
    var fromVal = document.getElementById('fromPicker').value;
    var toVal = document.getElementById('toPicker').value;
    var indices = [];
    RAW_DATA.labels.forEach(function(label, idx) {
      // label format: YYYY-MM-DDTHH:MM:00Z
      // picker format: YYYY-MM-DDTHH:MM
      // Slice to first 16 chars for comparison
      var labelSlice = label.slice(0, 16);
      if (fromVal && labelSlice < fromVal) { return; }
      if (toVal && labelSlice > toVal) { return; }
      indices.push(idx);
    });
    return indices;
  }

  function applyFilter() {
    var indices = getFilteredIndices();
    var filteredLabels = indices.map(function(i) { return RAW_DATA.labels[i]; });
    var series = currentView === 'tokens' ? RAW_DATA.token_series : RAW_DATA.cost_series;
    var filteredDatasets = series.map(function(s) {
      return { label: s.label, data: indices.map(function(i) { return s.data[i]; }) };
    });
    renderChart(filteredLabels, filteredDatasets);
  }

  // Toggle button
  document.getElementById('toggleBtn').addEventListener('click', function() {
    if (currentView === 'tokens') {
      currentView = 'cost';
      this.textContent = 'Switch to Token Counts';
      window.chart.options.plugins.title.text = 'Token Cost Over Time';
      window.chart.options.scales.y.title.text = 'Cost (USD)';
    } else {
      currentView = 'tokens';
      this.textContent = 'Switch to Cost USD';
      window.chart.options.plugins.title.text = 'Token Usage Over Time';
      window.chart.options.scales.y.title.text = 'Tokens';
    }
    applyFilter();
  });

  // Date pickers
  document.getElementById('fromPicker').addEventListener('change', function() {
    applyFilter();
  });
  document.getElementById('toPicker').addEventListener('change', function() {
    applyFilter();
  });

  // Reset button
  document.getElementById('resetBtn').addEventListener('click', function() {
    document.getElementById('fromPicker').value = '';
    document.getElementById('toPicker').value = '';
    applyFilter();
  });

})();
"""

    html = (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <title>Token Usage Report</title>\n"
        "  <style>\n"
        "    body { font-family: sans-serif; margin: 2rem; }\n"
        "    h1 { margin-bottom: 1rem; }\n"
        "    table { border-collapse: collapse; width: 100%; }\n"
        "    th, td { padding: 6px 12px; border: 1px solid #ccc; text-align: right; }\n"
        "    th:first-child, td:first-child { text-align: left; }\n"
        "    thead { background-color: #f0f0f0; }\n"
        "    tfoot { font-weight: bold; background-color: #e8e8e8; }\n"
        "    #chart-container { margin-top: 2rem; }\n"
        "    #controls { margin-bottom: 1rem; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>Token Usage Report</h1>\n"
        "  <table>\n"
        "    <thead>\n"
        "      <tr>\n"
        "        <th>Agent</th>\n"
        "        <th>Input Tokens</th>\n"
        "        <th>Output Tokens</th>\n"
        "        <th>Cache Read Tokens</th>\n"
        "        <th>Cache Write Tokens</th>\n"
        "        <th>Total Cost (USD)</th>\n"
        "      </tr>\n"
        "    </thead>\n"
        "    <tbody>\n"
        + tbody + "\n"
        "    </tbody>\n"
        "    <tfoot>\n"
        + tfoot_row + "\n"
        "    </tfoot>\n"
        "  </table>\n"
        "  <div id=\"chart-container\">\n"
        "    <div id=\"controls\">\n"
        "      <button id=\"toggleBtn\">Switch to Cost USD</button>\n"
        "      <label>From: <input type=\"datetime-local\" id=\"fromPicker\"></label>\n"
        "      <label>To: <input type=\"datetime-local\" id=\"toPicker\"></label>\n"
        "      <button id=\"resetBtn\">Reset</button>\n"
        "    </div>\n"
        "    <canvas id=\"tokenChart\"></canvas>\n"
        "  </div>\n"
        "<script>" + chartjs_src + "</script>\n"
        "<script>\n"
        + chart_init_js +
        "</script>\n"
        "</body>\n"
        "</html>\n"
    )

    return html


# ---------------------------------------------------------------------------
# 6. Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """Orchestrate loading, aggregation, HTML generation, and file output."""
    args = parse_args()
    tokens_dir = Path(args.tokens_dir)

    records = load_records(tokens_dir)
    agg = aggregate(records)

    cache_dir = Path(__file__).parent / ".chartjs_cache"
    chartjs_src = fetch_chartjs(cache_dir)

    html = build_html(agg, chartjs_src)

    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    output_path = Path.cwd() / f"token-report_{timestamp}.html"
    output_path.write_text(html, encoding="utf-8")

    print(str(output_path.resolve()))


if __name__ == "__main__":
    main()
