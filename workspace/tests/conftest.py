"""Shared pytest fixtures for token_report tests."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Sample JSONL data
# ---------------------------------------------------------------------------

SAMPLE_RECORDS = [
    {
        "ts": "2026-03-30T12:00:00Z",
        "agent": "designer",
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_tokens": 200,
        "cache_write_tokens": 10,
        "cost_usd": 0.000123,
    },
    {
        "ts": "2026-03-30T12:00:30Z",
        "agent": "designer",
        "input_tokens": 80,
        "output_tokens": 40,
        "cache_read_tokens": 150,
        "cache_write_tokens": 5,
        "cost_usd": 0.000099,
    },
    {
        "ts": "2026-03-30T12:01:00Z",
        "agent": "designer",
        "input_tokens": 60,
        "output_tokens": 30,
        "cache_read_tokens": 100,
        "cache_write_tokens": 0,
        "cost_usd": 0.000075,
    },
    {
        "ts": "2026-03-30T12:00:00Z",
        "agent": "ba",
        "input_tokens": 200,
        "output_tokens": 100,
        "cache_read_tokens": 500,
        "cache_write_tokens": 20,
        "cost_usd": 0.000250,
    },
    {
        "ts": "2026-03-30T12:02:00Z",
        "agent": "ba",
        "input_tokens": 150,
        "output_tokens": 75,
        "cache_read_tokens": 300,
        "cache_write_tokens": 15,
        "cost_usd": 0.000180,
    },
]


@pytest.fixture()
def sample_records() -> list[dict]:
    """Return a clean copy of the sample records list."""
    return [r.copy() for r in SAMPLE_RECORDS]


@pytest.fixture()
def tokens_dir(tmp_path: Path) -> Path:
    """Create a temporary tokens directory with two populated JSONL files.

    Layout:
        <tmp>/tokens/
            designer.jsonl  — 3 records
            ba.jsonl        — 2 records
    """
    d = tmp_path / "tokens"
    d.mkdir()

    designer_records = [r for r in SAMPLE_RECORDS if r["agent"] == "designer"]
    ba_records = [r for r in SAMPLE_RECORDS if r["agent"] == "ba"]

    _write_jsonl(d / "designer.jsonl", designer_records)
    _write_jsonl(d / "ba.jsonl", ba_records)

    return d


@pytest.fixture()
def tokens_dir_with_bad_lines(tmp_path: Path) -> Path:
    """Tokens directory that contains some unparseable lines mixed in."""
    d = tmp_path / "tokens"
    d.mkdir()

    lines = [
        json.dumps(SAMPLE_RECORDS[0]),
        "this is not json {{{",
        "",  # blank line
        json.dumps(SAMPLE_RECORDS[1]),
    ]
    (d / "designer.jsonl").write_text("\n".join(lines), encoding="utf-8")
    return d


@pytest.fixture()
def empty_tokens_dir(tmp_path: Path) -> Path:
    """Tokens directory that exists but contains no .jsonl files."""
    d = tmp_path / "tokens"
    d.mkdir()
    return d


@pytest.fixture()
def fake_chartjs() -> str:
    """A minimal fake Chart.js source string suitable for embedding in tests."""
    return textwrap.dedent("""\
        /* fake chart.js */
        (function(global){
          global.Chart = function(ctx, config){ this.config = config; };
          global.Chart.prototype.destroy = function(){};
          global.Chart.prototype.update = function(){};
        })(typeof window !== 'undefined' ? window : this);
    """)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, records: list[dict]) -> None:
    """Write a list of dicts to a JSONL file (one JSON object per line)."""
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )
