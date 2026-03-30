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
    # TODO: implement
    raise NotImplementedError


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
      - Toggle button (Token Counts / Cost USD view)
      - From/To datetime pickers + Reset button
      - A Chart.js canvas with all data embedded as a JSON literal
      - The Chart.js bundle inlined in a <script> tag
    """
    # TODO: implement
    raise NotImplementedError


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
