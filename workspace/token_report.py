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


def render_summary_table(per_agent_totals, grand_total):
    """Render the summary table HTML.

    Args:
        per_agent_totals: Dict of agent totals
        grand_total: Dict of grand totals

    Returns:
        HTML string for the table (stub)
    """
    # TODO: Implemented in a later story
    return "<table></table>"


def render_chart_html(minute_buckets):
    """Render the interactive chart HTML and JavaScript.

    Args:
        minute_buckets: List of aggregated minute bucket records

    Returns:
        HTML and JavaScript string (stub)
    """
    # TODO: Implemented in a later story
    return ""


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
    chart_html = render_chart_html(minute_buckets)

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
    <script>
    {chartjs_bundle}
    </script>
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
