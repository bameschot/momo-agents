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
import sys
from datetime import datetime
from pathlib import Path


def load_records(tokens_dir):
    """Load token records from JSONL files in tokens directory.

    Args:
        tokens_dir: Path object pointing to the tokens directory

    Returns:
        List of record dicts (empty list as stub)
    """
    # TODO: Implemented in a later story
    return []


def aggregate(records):
    """Aggregate records by minute bucket and compute totals.

    Args:
        records: List of record dicts

    Returns:
        Tuple of (minute_buckets, per_agent_totals, grand_total) (stubs)
    """
    # TODO: Implemented in a later story
    return [], {}, {}


def get_chartjs_bundle():
    """Get the Chart.js JavaScript bundle (inline).

    Returns:
        String containing Chart.js source code (stub)
    """
    # TODO: Implemented in a later story
    return ""


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
    minute_buckets, per_agent_totals, grand_total = aggregate(records)

    # Get Chart.js bundle
    chartjs_bundle = get_chartjs_bundle()

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
