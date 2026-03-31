"""Tests for the data loading / JSONL parsing logic (load_records)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from token_report import load_records


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


def test_load_records_basic() -> None:
    """Load a single file with valid JSON records."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create a simple JSONL file
        record1 = make_record("designer", "2026-03-30T12:55:10Z", 1, 10)
        record2 = make_record("designer", "2026-03-30T12:55:20Z", 2, 20)
        jsonl_content = "\n".join([json.dumps(record1), json.dumps(record2)])

        jsonl_file = tmppath / "designer.jsonl"
        jsonl_file.write_text(jsonl_content)

        records = load_records(tmppath)
        assert len(records) == 2
        assert records[0]["ts"] == "2026-03-30T12:55:10Z"
        assert records[0]["agent"] == "designer"
        assert records[1]["ts"] == "2026-03-30T12:55:20Z"


def test_load_records_multiple_agents() -> None:
    """Load files from multiple agents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create JSONL files for two agents
        designer_record = make_record("designer", "2026-03-30T12:55:10Z", 1, 10)
        architect_record = make_record("architect", "2026-03-30T12:55:10Z", 2, 20)

        (tmppath / "designer.jsonl").write_text(json.dumps(designer_record))
        (tmppath / "architect.jsonl").write_text(json.dumps(architect_record))

        records = load_records(tmppath)
        assert len(records) == 2

        agents = {r["agent"] for r in records}
        assert agents == {"designer", "architect"}


def test_load_records_skips_blank_lines() -> None:
    """Blank lines in JSONL files are silently skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        record1 = make_record("designer", "2026-03-30T12:55:10Z", 1, 10)
        record2 = make_record("designer", "2026-03-30T12:55:20Z", 2, 20)

        # File with blank lines
        jsonl_content = f"{json.dumps(record1)}\n\n{json.dumps(record2)}\n\n"
        (tmppath / "designer.jsonl").write_text(jsonl_content)

        records = load_records(tmppath)
        assert len(records) == 2


def test_load_records_skips_invalid_json() -> None:
    """Lines that fail JSON parsing are skipped with a warning to stderr."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        record1 = make_record("designer", "2026-03-30T12:55:10Z", 1, 10)
        record2 = make_record("designer", "2026-03-30T12:55:20Z", 2, 20)

        # File with one valid, one invalid, one valid line
        jsonl_content = f"{json.dumps(record1)}\n{{'invalid': json}}\n{json.dumps(record2)}"
        (tmppath / "designer.jsonl").write_text(jsonl_content)

        # Capture stderr to verify warning is printed
        import io
        from contextlib import redirect_stderr

        stderr_capture = io.StringIO()
        with redirect_stderr(stderr_capture):
            records = load_records(tmppath)

        assert len(records) == 2
        stderr_output = stderr_capture.getvalue()
        assert "Warning" in stderr_output or "Failed to parse" in stderr_output


def test_load_records_empty_directory() -> None:
    """No *.jsonl files in directory returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        records = load_records(tmppath)
        assert len(records) == 0


def test_load_records_two_files_with_malformed_lines() -> None:
    """Load two JSONL files with mixed valid and malformed lines."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        record1 = make_record("designer", "2026-03-30T12:55:10Z", 1, 10)
        record2 = make_record("designer", "2026-03-30T12:55:20Z", 2, 20)
        record3 = make_record("architect", "2026-03-30T12:55:10Z", 3, 30)
        record4 = make_record("architect", "2026-03-30T12:55:20Z", 4, 40)

        # Designer file: 2 valid records and 1 malformed line
        designer_content = f"{json.dumps(record1)}\n{{'bad': json}}\n{json.dumps(record2)}"
        (tmppath / "designer.jsonl").write_text(designer_content)

        # Architect file: 2 valid records and 1 malformed line
        architect_content = f"{json.dumps(record3)}\ninvalid line\n{json.dumps(record4)}"
        (tmppath / "architect.jsonl").write_text(architect_content)

        records = load_records(tmppath)
        # Should have 4 valid records total (2 from each file)
        assert len(records) == 4

        agent_counts = {}
        for record in records:
            agent = record["agent"]
            agent_counts[agent] = agent_counts.get(agent, 0) + 1

        assert agent_counts["designer"] == 2
        assert agent_counts["architect"] == 2
