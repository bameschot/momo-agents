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
import sys
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
    # TODO: implement
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


def aggregate_by_minute(records: list[dict]) -> list[dict]:
    """Group records by (agent, minute bucket) and sum token/cost fields.

    The minute bucket is the ISO-8601 timestamp truncated to the minute,
    e.g. '2026-03-30T12:55:00Z'.

    Returns a list of aggregated dicts sorted by (minute, agent).
    """
    # TODO: implement
    raise NotImplementedError


def compute_agent_totals(records: list[dict]) -> dict[str, dict]:
    """Compute per-agent totals across all time.

    Returns a dict keyed by agent name, each value being a dict with:
        input_tokens, output_tokens, cache_read_tokens,
        cache_write_tokens, cost_usd
    """
    # TODO: implement
    raise NotImplementedError


def compute_grand_total(agent_totals: dict[str, dict]) -> dict:
    """Sum all agents into a single grand-total dict."""
    # TODO: implement
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Chart.js Bundle
# ---------------------------------------------------------------------------


def get_chartjs_source() -> str:
    """Return the Chart.js UMD source, using a local cache when available.

    Downloads from CHARTJS_URL on first run and caches to CHARTJS_CACHE_PATH.
    """
    # TODO: implement
    raise NotImplementedError


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
    # TODO: implement
    raise NotImplementedError


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
    # TODO: implement
    raise NotImplementedError


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
