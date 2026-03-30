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
from datetime import datetime, timezone
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
      - A <div id="chart-container"> placeholder for the chart (added in STORY-007)
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
        "  <div id=\"chart-container\"></div>\n"
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

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    output_path = Path.cwd() / f"token-report_{timestamp}.html"
    output_path.write_text(html, encoding="utf-8")

    print(str(output_path))


if __name__ == "__main__":
    main()
