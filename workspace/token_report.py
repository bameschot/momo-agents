#!/usr/bin/env python3
"""
Token Usage Report Generator

Reads per-agent token usage logs from .sentinels/tokens/*.jsonl, aggregates the data,
and produces a self-contained single-page HTML report with interactive Chart.js
visualizations for token counts and costs.

Usage:
    python token_report.py [--tokens-dir <path>]

Output:
    token-report_YYYY-MM-DD_HH-MM-SS.html (written to CWD)
"""

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def load_records(tokens_dir):
    """Load token records from JSONL files in tokens directory.

    Discovers all *.jsonl files in the tokens directory, parses each line as JSON,
    derives agent names from filenames, and returns a list of record dicts.
    Skips blank lines silently; invalid JSON lines are skipped with a warning.
    Exits with code 1 if no .jsonl files are found.

    Args:
        tokens_dir: Path object pointing to the tokens directory

    Returns:
        List of record dicts with keys: ts, agent, input_tokens, output_tokens,
        cache_read_tokens, cache_write_tokens, cost_usd
    """
    records = []

    # Discover all *.jsonl files in the directory
    jsonl_files = list(tokens_dir.glob("*.jsonl"))

    # Check if any files were found
    if not jsonl_files:
        print(
            f"Error: no .jsonl files found in {tokens_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Parse each file
    for filepath in jsonl_files:
        agent_name = filepath.stem
        try:
            with open(filepath, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip blank lines silently
                    if not line:
                        continue

                    # Parse JSON line
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as e:
                        print(
                            f"Warning: invalid JSON in {filepath}:{line_num} - "
                            f"skipping. Error: {e}",
                            file=sys.stderr,
                        )
                        continue

                    # Inject agent name
                    record["agent"] = agent_name
                    records.append(record)
        except OSError as e:
            print(
                f"Warning: error reading {filepath} - skipping. Error: {e}",
                file=sys.stderr,
            )
            continue

    return records


def aggregate(records):
    """Aggregate records by minute bucket and compute totals.

    Groups records by (agent, minute) where minute is the record's timestamp
    truncated to YYYY-MM-DDTHH:MM:00Z. Computes sums of all numeric fields
    within each bucket, per-agent totals, and a grand total across all agents.

    Args:
        records: List of record dicts with keys: ts, agent, input_tokens,
                 output_tokens, cache_read_tokens, cache_write_tokens, cost_usd

    Returns:
        Dict with keys:
        - "buckets": list of aggregated minute-bucket dicts, sorted by minute
                     then agent
        - "agent_totals": list of per-agent total dicts, with all numeric fields
                          summed across all time
        - "grand_total": dict with all numeric fields summed across all agents
                         (agent field set to "Total")
    """
    # Use defaultdict to accumulate bucket sums
    bucket_data = defaultdict(lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "cost_usd": 0.0,
    })

    # Use defaultdict for agent totals
    agent_totals_data = defaultdict(lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "cost_usd": 0.0,
    })

    # Process each record
    for record in records:
        # Truncate timestamp to minute bucket
        ts = record["ts"]
        minute = ts[:16] + ":00Z"  # YYYY-MM-DDTHH:MM:00Z

        # Bucket key
        bucket_key = (record["agent"], minute)

        # Accumulate bucket data
        bucket_data[bucket_key]["input_tokens"] += record.get(
            "input_tokens", 0
        )
        bucket_data[bucket_key]["output_tokens"] += record.get(
            "output_tokens", 0
        )
        bucket_data[bucket_key]["cache_read_tokens"] += record.get(
            "cache_read_tokens", 0
        )
        bucket_data[bucket_key]["cache_write_tokens"] += record.get(
            "cache_write_tokens", 0
        )
        bucket_data[bucket_key]["cost_usd"] += record.get("cost_usd", 0.0)

        # Accumulate agent totals
        agent = record["agent"]
        agent_totals_data[agent]["input_tokens"] += record.get(
            "input_tokens", 0
        )
        agent_totals_data[agent]["output_tokens"] += record.get(
            "output_tokens", 0
        )
        agent_totals_data[agent]["cache_read_tokens"] += record.get(
            "cache_read_tokens", 0
        )
        agent_totals_data[agent]["cache_write_tokens"] += record.get(
            "cache_write_tokens", 0
        )
        agent_totals_data[agent]["cost_usd"] += record.get("cost_usd", 0.0)

    # Build buckets list with minute and agent fields
    buckets = []
    for (agent, minute), data in bucket_data.items():
        bucket = {"minute": minute, "agent": agent, **data}
        buckets.append(bucket)

    # Sort buckets by minute, then by agent
    buckets.sort(key=lambda x: (x["minute"], x["agent"]))

    # Build agent_totals list
    agent_totals = []
    for agent, data in agent_totals_data.items():
        total = {"agent": agent, **data}
        agent_totals.append(total)

    # Sort agent totals by agent name for deterministic ordering
    agent_totals.sort(key=lambda x: x["agent"])

    # Build grand total
    grand_total = {
        "agent": "Total",
        "input_tokens": sum(
            a["input_tokens"] for a in agent_totals
        ),
        "output_tokens": sum(
            a["output_tokens"] for a in agent_totals
        ),
        "cache_read_tokens": sum(
            a["cache_read_tokens"] for a in agent_totals
        ),
        "cache_write_tokens": sum(
            a["cache_write_tokens"] for a in agent_totals
        ),
        "cost_usd": sum(a["cost_usd"] for a in agent_totals),
    }

    return {
        "buckets": buckets,
        "agent_totals": agent_totals,
        "grand_total": grand_total,
    }


# Chart.js CDN URL for the UMD bundle
CHARTJS_CDN_URL = "https://cdn.jsdelivr.net/npm/chart.js/dist/chart.umd.min.js"


def get_chartjs_bundle(cache_dir):
    """Get the Chart.js JavaScript bundle (inline).

    Fetches the Chart.js UMD bundle and caches it locally to avoid repeated
    network requests. If the cached file exists, it is read and returned
    immediately. If not, the bundle is downloaded from the CDN, cached, and
    returned as a string.

    Args:
        cache_dir: Path object pointing to the directory where the cached
                   bundle will be stored

    Returns:
        String containing Chart.js source code (UTF-8 decoded)
    """
    cache_file = cache_dir / "chart.umd.min.js"

    # If cache file exists, read and return it
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    # Cache miss: download from CDN
    response = urllib.request.urlopen(CHARTJS_CDN_URL)
    bundle_bytes = response.read()
    bundle_str = bundle_bytes.decode("utf-8")

    # Create cache directory if needed
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Write to cache
    cache_file.write_text(bundle_str, encoding="utf-8")

    return bundle_str


def render_summary_table(agent_totals, grand_total):
    """Render the summary table HTML showing per-agent token counts and costs.

    Generates an HTML table with one row per agent plus a grand-total row.
    Integer token counts are formatted with thousands separators (e.g., 1,234,567).
    Cost values are formatted to exactly 6 decimal places (e.g., 0.012345).

    Args:
        agent_totals: List of per-agent total dicts, each containing:
                     agent, input_tokens, output_tokens, cache_read_tokens,
                     cache_write_tokens, cost_usd
        grand_total: Dict with aggregated totals across all agents,
                    containing the same keys as agent_totals entries

    Returns:
        HTML string containing a <table> element with styled rows and cells
    """
    # Build header row
    header = (
        "<tr>"
        "<th>Agent</th>"
        "<th style='text-align: right;'>Input Tokens</th>"
        "<th style='text-align: right;'>Output Tokens</th>"
        "<th style='text-align: right;'>Cache Read Tokens</th>"
        "<th style='text-align: right;'>Cache Write Tokens</th>"
        "<th style='text-align: right;'>Total Cost (USD)</th>"
        "</tr>"
    )

    # Build data rows for each agent
    data_rows = []
    for agent_total in agent_totals:
        agent = agent_total["agent"]
        input_tokens = agent_total["input_tokens"]
        output_tokens = agent_total["output_tokens"]
        cache_read = agent_total["cache_read_tokens"]
        cache_write = agent_total["cache_write_tokens"]
        cost = agent_total["cost_usd"]

        row = (
            "<tr>"
            f"<td>{agent}</td>"
            f"<td style='text-align: right;'>{input_tokens:,}</td>"
            f"<td style='text-align: right;'>{output_tokens:,}</td>"
            f"<td style='text-align: right;'>{cache_read:,}</td>"
            f"<td style='text-align: right;'>{cache_write:,}</td>"
            f"<td style='text-align: right;'>{cost:.6f}</td>"
            "</tr>"
        )
        data_rows.append(row)

    # Build grand total row
    input_tokens = grand_total["input_tokens"]
    output_tokens = grand_total["output_tokens"]
    cache_read = grand_total["cache_read_tokens"]
    cache_write = grand_total["cache_write_tokens"]
    cost = grand_total["cost_usd"]

    total_row = (
        "<tr class='total-row'>"
        "<th>Total</th>"
        f"<th style='text-align: right;'>{input_tokens:,}</th>"
        f"<th style='text-align: right;'>{output_tokens:,}</th>"
        f"<th style='text-align: right;'>{cache_read:,}</th>"
        f"<th style='text-align: right;'>{cache_write:,}</th>"
        f"<th style='text-align: right;'>{cost:.6f}</th>"
        "</tr>"
    )

    # Assemble table
    table_content = header + "".join(data_rows) + total_row
    html = f"<table>\n{table_content}\n</table>"

    return html


def render_chart_html(buckets, chartjs_src):
    """Render the interactive Chart.js chart section as a self-contained HTML fragment.

    Generates an HTML fragment containing the Chart.js library (embedded verbatim),
    interactive controls (toggle button, datetime-range pickers, reset button),
    a canvas element, and an inline script that embeds all aggregated data as a
    JSON literal and implements client-side interactivity.

    Args:
        buckets: List of aggregated minute-bucket dicts, each containing:
                 minute, agent, input_tokens, output_tokens, cache_read_tokens,
                 cache_write_tokens, cost_usd
        chartjs_src: String containing the Chart.js source code to embed inline

    Returns:
        HTML string containing the full interactive chart section
    """
    token_types = ["input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"]
    palette = [
        "#4dc9f6", "#f67019", "#f53794", "#537bc4", "#acc236",
        "#166a8f", "#00a950", "#58595b", "#8549ba", "#e8c534",
        "#d35400", "#27ae60", "#2980b9", "#8e44ad", "#c0392b",
    ]

    # Deduplicate and sort minutes and agents from the full bucket list
    all_minutes = sorted({b["minute"] for b in buckets})
    all_agents = sorted({b["agent"] for b in buckets})

    # Pre-compute token count datasets (one per agent × token_type)
    token_datasets = []
    color_idx = 0
    for agent in all_agents:
        for tt in token_types:
            data = []
            for m in all_minutes:
                matching = [b for b in buckets if b["agent"] == agent and b["minute"] == m]
                data.append(matching[0][tt] if matching else 0)
            token_datasets.append({
                "label": f"{agent} \u00b7 {tt}",
                "data": data,
                "borderColor": palette[color_idx % len(palette)],
                "backgroundColor": palette[color_idx % len(palette)],
                "fill": False,
                "tension": 0.1,
            })
            color_idx += 1

    # Pre-compute cost datasets (one per agent)
    cost_datasets = []
    for i, agent in enumerate(all_agents):
        data = []
        for m in all_minutes:
            matching = [b for b in buckets if b["agent"] == agent and b["minute"] == m]
            data.append(matching[0]["cost_usd"] if matching else 0)
        cost_datasets.append({
            "label": f"{agent} \u00b7 cost_usd",
            "data": data,
            "borderColor": palette[i % len(palette)],
            "backgroundColor": palette[i % len(palette)],
            "fill": False,
            "tension": 0.1,
        })

    buckets_json = json.dumps(buckets, default=str)
    all_minutes_json = json.dumps(all_minutes)
    token_datasets_json = json.dumps(token_datasets, default=str, ensure_ascii=False)
    cost_datasets_json = json.dumps(cost_datasets, default=str, ensure_ascii=False)

    return f"""<script>{chartjs_src}</script>
<div style="margin: 20px 0;">
  <button id="toggleBtn" onclick="toggleView()">Switch to Cost USD</button>
  &nbsp;
  <label>From: <input type="datetime-local" id="fromPicker" onchange="applyFilter()"></label>
  &nbsp;
  <label>To: <input type="datetime-local" id="toPicker" onchange="applyFilter()"></label>
  &nbsp;
  <button id="resetBtn" onclick="resetFilter()">Reset</button>
</div>
<canvas id="tokenChart"></canvas>
<script>
(function() {{
  const RAW_BUCKETS = {buckets_json};
  const ALL_MINUTES = {all_minutes_json};
  const TOKEN_DATASETS = {token_datasets_json};
  const COST_DATASETS = {cost_datasets_json};

  let currentView = 'tokens';
  let chart = null;

  function getFilteredIndices() {{
    const fromVal = document.getElementById('fromPicker').value;
    const toVal = document.getElementById('toPicker').value;
    const indices = [];
    ALL_MINUTES.forEach(function(m, i) {{
      if (fromVal && m < fromVal) return;
      if (toVal && m > toVal) return;
      indices.push(i);
    }});
    return indices;
  }}

  function filterDatasets(datasets, indices) {{
    return datasets.map(function(ds) {{
      return Object.assign({{}}, ds, {{
        data: indices.map(function(i) {{ return ds.data[i]; }})
      }});
    }});
  }}

  function renderChart() {{
    const indices = getFilteredIndices();
    const labels = indices.map(function(i) {{ return ALL_MINUTES[i]; }});
    const isTokenView = currentView === 'tokens';
    const datasets = isTokenView
      ? filterDatasets(TOKEN_DATASETS, indices)
      : filterDatasets(COST_DATASETS, indices);
    const yLabel = isTokenView ? 'Token Count' : 'Cost (USD)';
    const title = isTokenView ? 'Token Usage Over Time' : 'Cost Over Time';

    const ctx = document.getElementById('tokenChart').getContext('2d');
    if (chart) {{
      chart.destroy();
    }}
    chart = new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: labels,
        datasets: datasets
      }},
      options: {{
        responsive: true,
        plugins: {{
          title: {{
            display: true,
            text: title
          }},
          legend: {{
            display: true
          }}
        }},
        scales: {{
          y: {{
            title: {{
              display: true,
              text: yLabel
            }}
          }}
        }}
      }}
    }});
  }}

  function toggleView() {{
    if (currentView === 'tokens') {{
      currentView = 'cost';
      document.getElementById('toggleBtn').textContent = 'Switch to Token Counts';
    }} else {{
      currentView = 'tokens';
      document.getElementById('toggleBtn').textContent = 'Switch to Cost USD';
    }}
    renderChart();
  }}

  function applyFilter() {{
    renderChart();
  }}

  function resetFilter() {{
    document.getElementById('fromPicker').value = '';
    document.getElementById('toPicker').value = '';
    renderChart();
  }}

  window.toggleView = toggleView;
  window.applyFilter = applyFilter;
  window.resetFilter = resetFilter;

  document.addEventListener('DOMContentLoaded', function() {{
    renderChart();
  }});
}})();
</script>"""


def main():
    """Main entry point.

    Parses arguments, validates the tokens directory, loads and aggregates data,
    and generates an HTML report.
    """
    parser = argparse.ArgumentParser(
        description="Generate a token usage report from .sentinels/tokens/*.jsonl"
    )
    parser.add_argument(
        "--tokens-dir",
        default=".sentinels/tokens",
        help="Path to directory containing *.jsonl files (default: .sentinels/tokens)",
    )
    args = parser.parse_args()

    tokens_dir = Path(args.tokens_dir)

    # Validate tokens directory
    if not tokens_dir.is_dir():
        print(f"Error: tokens directory not found: {tokens_dir}", file=sys.stderr)
        sys.exit(1)

    # Load and aggregate records
    records = load_records(tokens_dir)
    result = aggregate(records)
    minute_buckets = result["buckets"]
    per_agent_totals = result["agent_totals"]
    grand_total = result["grand_total"]

    # Get Chart.js bundle
    cache_dir = Path("workspace/.chartjs_cache")
    chartjs_bundle = get_chartjs_bundle(cache_dir)

    # Render report components
    summary_table = render_summary_table(per_agent_totals, grand_total)
    chart_html = render_chart_html(minute_buckets, chartjs_bundle)

    # Assemble HTML
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Token Usage Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f9f9f9;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Token Usage Report</h1>
        {summary_table}
        {chart_html}
    </div>
</body>
</html>"""

    # Generate output filename
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    output_filename = f"token-report_{timestamp}.html"
    output_path = Path(output_filename)

    # Write HTML to file
    output_path.write_text(html_content)

    # Print the path to stdout
    print(str(output_path))

    # Exit with success
    sys.exit(0)


if __name__ == "__main__":
    main()
