"""Tests for the aggregation logic (minute-bucket grouping and per-agent totals)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from token_report import aggregate_by_minute, compute_agent_totals, compute_grand_total


def make_record(
    agent: str,
    ts: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    cost_usd: float = 0.0,
) -> dict:
    """Helper to create a test record dict."""
    return {
        "ts": ts,
        "agent": agent,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "cost_usd": cost_usd,
    }


def test_aggregate_same_minute_same_agent() -> None:
    """Two records in the same minute for the same agent are summed."""
    records = [
        make_record("designer", "2026-03-30T12:55:10Z", input_tokens=3, output_tokens=10),
        make_record("designer", "2026-03-30T12:55:40Z", input_tokens=7, output_tokens=20),
    ]
    buckets = aggregate_by_minute(records)

    assert len(buckets) == 1
    assert buckets[0]["minute"] == "2026-03-30T12:55:00Z"
    assert buckets[0]["agent"] == "designer"
    assert buckets[0]["input_tokens"] == 10
    assert buckets[0]["output_tokens"] == 30


def test_aggregate_different_minutes() -> None:
    """Two records in different minutes for the same agent are separate."""
    records = [
        make_record("designer", "2026-03-30T12:55:10Z", input_tokens=3, output_tokens=10),
        make_record("designer", "2026-03-30T12:56:10Z", input_tokens=7, output_tokens=20),
    ]
    buckets = aggregate_by_minute(records)

    assert len(buckets) == 2
    assert buckets[0]["minute"] == "2026-03-30T12:55:00Z"
    assert buckets[1]["minute"] == "2026-03-30T12:56:00Z"


def test_aggregate_different_agents_same_minute() -> None:
    """Two records for different agents in the same minute are separate."""
    records = [
        make_record("designer", "2026-03-30T12:55:10Z", input_tokens=3, output_tokens=10),
        make_record("architect", "2026-03-30T12:55:40Z", input_tokens=7, output_tokens=20),
    ]
    buckets = aggregate_by_minute(records)

    assert len(buckets) == 2
    # Sorted by (minute, agent)
    assert buckets[0]["agent"] == "architect"
    assert buckets[1]["agent"] == "designer"


def test_aggregate_cost_usd_summed() -> None:
    """Cost fields are summed correctly."""
    records = [
        make_record("designer", "2026-03-30T12:55:10Z", cost_usd=0.001234),
        make_record("designer", "2026-03-30T12:55:40Z", cost_usd=0.005678),
    ]
    buckets = aggregate_by_minute(records)

    assert len(buckets) == 1
    # Allow for floating point precision
    assert abs(buckets[0]["cost_usd"] - 0.006912) < 1e-9


def test_aggregate_empty_records() -> None:
    """Empty records list returns empty list."""
    buckets = aggregate_by_minute([])
    assert len(buckets) == 0


def test_compute_agent_totals_basic() -> None:
    """Per-agent totals sum correctly across all time."""
    records = [
        make_record("designer", "2026-03-30T12:55:10Z", input_tokens=3, output_tokens=10),
        make_record("designer", "2026-03-30T12:56:10Z", input_tokens=7, output_tokens=20),
        make_record("architect", "2026-03-30T12:55:10Z", input_tokens=5, output_tokens=15),
    ]
    totals = compute_agent_totals(records)

    assert len(totals) == 2
    assert totals["designer"]["input_tokens"] == 10
    assert totals["designer"]["output_tokens"] == 30
    assert totals["architect"]["input_tokens"] == 5
    assert totals["architect"]["output_tokens"] == 15


def test_compute_agent_totals_empty() -> None:
    """Empty records list returns empty dict."""
    totals = compute_agent_totals([])
    assert len(totals) == 0


def test_compute_grand_total() -> None:
    """Grand total sums across all agents."""
    agent_totals = {
        "designer": {
            "input_tokens": 10,
            "output_tokens": 30,
            "cache_read_tokens": 100,
            "cache_write_tokens": 0,
            "cost_usd": 0.01,
        },
        "architect": {
            "input_tokens": 5,
            "output_tokens": 15,
            "cache_read_tokens": 50,
            "cache_write_tokens": 0,
            "cost_usd": 0.005,
        },
    }
    grand = compute_grand_total(agent_totals)

    assert grand["input_tokens"] == 15
    assert grand["output_tokens"] == 45
    assert grand["cache_read_tokens"] == 150
    assert grand["cache_write_tokens"] == 0
    assert abs(grand["cost_usd"] - 0.015) < 1e-9


def test_compute_grand_total_empty() -> None:
    """Empty agent totals returns zero dict."""
    grand = compute_grand_total({})
    assert grand["input_tokens"] == 0
    assert grand["output_tokens"] == 0
    assert grand["cache_read_tokens"] == 0
    assert grand["cache_write_tokens"] == 0
    assert grand["cost_usd"] == 0.0
