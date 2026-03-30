"""Tests for aggregate() in token_report.py."""

from __future__ import annotations

import pytest

from token_report import aggregate

# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------

def test_aggregate_empty_returns_zero_structure():
    result = aggregate([])
    assert result == {
        "buckets": [],
        "agent_totals": {},
        "grand_total": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "cost_usd": 0.0,
        },
    }


# ---------------------------------------------------------------------------
# Bucket merging: same (agent, minute) are combined
# ---------------------------------------------------------------------------

def test_same_agent_same_minute_merged_into_one_bucket():
    """Two records with identical (agent, minute) must produce one bucket."""
    records = [
        {
            "ts": "2026-03-30T12:00:05Z",
            "agent": "designer",
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 200,
            "cache_write_tokens": 10,
            "cost_usd": 0.0001,
        },
        {
            "ts": "2026-03-30T12:00:45Z",
            "agent": "designer",
            "input_tokens": 80,
            "output_tokens": 40,
            "cache_read_tokens": 150,
            "cache_write_tokens": 5,
            "cost_usd": 0.00009,
        },
    ]
    result = aggregate(records)
    assert len(result["buckets"]) == 1
    bucket = result["buckets"][0]
    assert bucket["minute"] == "2026-03-30T12:00:00Z"
    assert bucket["agent"] == "designer"
    assert bucket["input_tokens"] == 180
    assert bucket["output_tokens"] == 90
    assert bucket["cache_read_tokens"] == 350
    assert bucket["cache_write_tokens"] == 15
    assert pytest.approx(bucket["cost_usd"]) == 0.00019


# ---------------------------------------------------------------------------
# Different minutes → separate buckets
# ---------------------------------------------------------------------------

def test_different_minutes_produce_separate_buckets():
    """Records in different minutes for the same agent produce separate bucket rows."""
    records = [
        {
            "ts": "2026-03-30T12:00:10Z",
            "agent": "designer",
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "cost_usd": 0.0001,
        },
        {
            "ts": "2026-03-30T12:01:20Z",
            "agent": "designer",
            "input_tokens": 60,
            "output_tokens": 30,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "cost_usd": 0.00006,
        },
    ]
    result = aggregate(records)
    assert len(result["buckets"]) == 2
    minutes = [b["minute"] for b in result["buckets"]]
    assert "2026-03-30T12:00:00Z" in minutes
    assert "2026-03-30T12:01:00Z" in minutes


# ---------------------------------------------------------------------------
# Multi-agent fixture
# ---------------------------------------------------------------------------

def test_aggregate_with_sample_records(sample_records):
    """Three records for designer, two for ba across different minutes."""
    result = aggregate(sample_records)

    # Buckets: designer has minutes 12:00 and 12:01; ba has minutes 12:00 and 12:02
    # So 4 distinct (agent, minute) pairs
    assert len(result["buckets"]) == 4

    # Agent totals keys
    assert set(result["agent_totals"].keys()) == {"designer", "ba"}

    # Designer totals
    designer = result["agent_totals"]["designer"]
    assert designer["input_tokens"] == 100 + 80 + 60  # 240
    assert designer["output_tokens"] == 50 + 40 + 30  # 120
    assert designer["cache_read_tokens"] == 200 + 150 + 100  # 450
    assert designer["cache_write_tokens"] == 10 + 5 + 0  # 15
    assert pytest.approx(designer["cost_usd"]) == 0.000123 + 0.000099 + 0.000075

    # Ba totals
    ba = result["agent_totals"]["ba"]
    assert ba["input_tokens"] == 200 + 150  # 350
    assert ba["output_tokens"] == 100 + 75  # 175
    assert ba["cache_read_tokens"] == 500 + 300  # 800
    assert ba["cache_write_tokens"] == 20 + 15  # 35
    assert pytest.approx(ba["cost_usd"]) == 0.000250 + 0.000180


def test_grand_total_equals_sum_of_all_records(sample_records):
    result = aggregate(sample_records)
    grand = result["grand_total"]

    total_input = sum(r["input_tokens"] for r in sample_records)
    total_output = sum(r["output_tokens"] for r in sample_records)
    total_cache_read = sum(r["cache_read_tokens"] for r in sample_records)
    total_cache_write = sum(r["cache_write_tokens"] for r in sample_records)
    total_cost = sum(r["cost_usd"] for r in sample_records)

    assert grand["input_tokens"] == total_input
    assert grand["output_tokens"] == total_output
    assert grand["cache_read_tokens"] == total_cache_read
    assert grand["cache_write_tokens"] == total_cache_write
    assert pytest.approx(grand["cost_usd"]) == total_cost


# ---------------------------------------------------------------------------
# Bucket sort order
# ---------------------------------------------------------------------------

def test_buckets_sorted_by_minute_then_agent(sample_records):
    """Buckets must be ordered by (minute, agent) ascending."""
    result = aggregate(sample_records)
    keys = [(b["minute"], b["agent"]) for b in result["buckets"]]
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# Minute truncation
# ---------------------------------------------------------------------------

def test_minute_truncation():
    """Seconds in ts must be replaced with ':00Z'."""
    records = [
        {
            "ts": "2026-03-30T09:59:59Z",
            "agent": "x",
            "input_tokens": 1,
            "output_tokens": 1,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "cost_usd": 0.0,
        }
    ]
    result = aggregate(records)
    assert result["buckets"][0]["minute"] == "2026-03-30T09:59:00Z"
