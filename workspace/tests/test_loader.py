"""Tests for the data loader component."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from token_report import load_records


class TestDataLoader:
    """Tests for the data loader component."""

    def test_valid_data_multiple_files(self):
        """Test loading valid data from multiple .jsonl files.

        Verify:
        - Correct number of records loaded
        - Agent names match filename stems
        - All expected fields are present
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create two test files
            designer_file = tmpdir_path / "designer.jsonl"
            designer_file.write_text(
                json.dumps({
                    "ts": "2026-03-30T12:00:00Z",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_read_tokens": 200,
                    "cache_write_tokens": 0,
                    "cost_usd": 0.001,
                }) + "\n"
                + json.dumps({
                    "ts": "2026-03-30T12:01:00Z",
                    "input_tokens": 150,
                    "output_tokens": 75,
                    "cache_read_tokens": 300,
                    "cache_write_tokens": 0,
                    "cost_usd": 0.0015,
                }) + "\n"
            )

            agent_file = tmpdir_path / "agent.jsonl"
            agent_file.write_text(
                json.dumps({
                    "ts": "2026-03-30T12:02:00Z",
                    "input_tokens": 200,
                    "output_tokens": 100,
                    "cache_read_tokens": 400,
                    "cache_write_tokens": 50,
                    "cost_usd": 0.002,
                }) + "\n"
            )

            # Load records
            records = load_records(tmpdir_path)

            # Assert correct number of records
            assert len(records) == 3, (
                f"Expected 3 records, got {len(records)}"
            )

            # Assert agent names
            agents = {r["agent"] for r in records}
            assert agents == {"designer", "agent"}, (
                f"Expected agents {{'designer', 'agent'}}, got {agents}"
            )

            # Assert expected fields are present
            for record in records:
                required_fields = {
                    "ts", "agent", "input_tokens", "output_tokens",
                    "cache_read_tokens", "cache_write_tokens", "cost_usd"
                }
                assert required_fields.issubset(record.keys()), (
                    f"Record missing required fields: {record}"
                )

    def test_invalid_lines_skipped(self, capsys):
        """Test that invalid JSON lines are skipped with a warning.

        Verify:
        - Only valid record is returned
        - Warning is printed to stderr
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a file with one valid and one invalid line
            test_file = tmpdir_path / "test.jsonl"
            test_file.write_text(
                json.dumps({
                    "ts": "2026-03-30T12:00:00Z",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_read_tokens": 200,
                    "cache_write_tokens": 0,
                    "cost_usd": 0.001,
                }) + "\n"
                + "not valid json\n"
            )

            # Load records
            records = load_records(tmpdir_path)

            # Assert only one valid record
            assert len(records) == 1, (
                f"Expected 1 record, got {len(records)}"
            )

            # Assert warning was printed
            captured = capsys.readouterr()
            assert "Warning" in captured.err, (
                f"Expected warning in stderr, got: {captured.err}"
            )
            assert "invalid JSON" in captured.err, (
                f"Expected 'invalid JSON' in stderr, got: {captured.err}"
            )

    def test_blank_lines_skipped_silently(self):
        """Test that blank lines are skipped silently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a file with blank lines
            test_file = tmpdir_path / "test.jsonl"
            test_file.write_text(
                json.dumps({
                    "ts": "2026-03-30T12:00:00Z",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_read_tokens": 200,
                    "cache_write_tokens": 0,
                    "cost_usd": 0.001,
                }) + "\n"
                + "\n"  # blank line
                + "\n"  # another blank line
                + json.dumps({
                    "ts": "2026-03-30T12:01:00Z",
                    "input_tokens": 150,
                    "output_tokens": 75,
                    "cache_read_tokens": 300,
                    "cache_write_tokens": 0,
                    "cost_usd": 0.0015,
                }) + "\n"
            )

            # Load records
            records = load_records(tmpdir_path)

            # Assert only two valid records (blank lines skipped)
            assert len(records) == 2, (
                f"Expected 2 records, got {len(records)}"
            )

    def test_no_files_found_exits_with_code_1(self):
        """Test that missing .jsonl files cause exit with code 1.

        Use subprocess to verify the exit code since load_records calls
        sys.exit().
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test script that calls load_records
            test_script = tmpdir_path / "test_script.py"
            test_script.write_text(
                f"""
import sys
sys.path.insert(0, '{Path(__file__).parent.parent}')
from token_report import load_records
from pathlib import Path

load_records(Path('{tmpdir_path}'))
"""
            )

            # Run the script
            result = subprocess.run(
                [sys.executable, str(test_script)],
                capture_output=True,
                text=True,
            )

            # Assert exit code is 1
            assert result.returncode == 1, (
                f"Expected exit code 1, got {result.returncode}. "
                f"stderr: {result.stderr}"
            )

            # Assert error message was printed
            assert "no .jsonl files found" in result.stderr, (
                f"Expected error message in stderr, got: {result.stderr}"
            )
