"""Integration tests for end-to-end token report generation."""

import json
import re
import subprocess
import tempfile
from pathlib import Path


class TestIntegration:
    """Integration tests for end-to-end report generation."""

    def test_full_run_with_sample_data(self):
        """Test complete report generation from JSONL to HTML.

        Verify:
        - Exit code is 0
        - stdout contains a filename matching token-report_YYYY-MM-DD_HH-MM-SS.html
        - The generated HTML file exists
        - The HTML contains both agent names
        - The HTML contains RAW_BUCKETS
        - The HTML contains <!DOCTYPE html>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create two sample .jsonl files with three records each
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
                + json.dumps({
                    "ts": "2026-03-30T12:02:00Z",
                    "input_tokens": 200,
                    "output_tokens": 100,
                    "cache_read_tokens": 400,
                    "cache_write_tokens": 50,
                    "cost_usd": 0.002,
                }) + "\n"
            )

            agent_file = tmpdir_path / "agent.jsonl"
            agent_file.write_text(
                json.dumps({
                    "ts": "2026-03-30T12:00:30Z",
                    "input_tokens": 300,
                    "output_tokens": 150,
                    "cache_read_tokens": 600,
                    "cache_write_tokens": 100,
                    "cost_usd": 0.003,
                }) + "\n"
                + json.dumps({
                    "ts": "2026-03-30T12:01:30Z",
                    "input_tokens": 250,
                    "output_tokens": 125,
                    "cache_read_tokens": 500,
                    "cache_write_tokens": 75,
                    "cost_usd": 0.0025,
                }) + "\n"
                + json.dumps({
                    "ts": "2026-03-30T12:02:30Z",
                    "input_tokens": 350,
                    "output_tokens": 175,
                    "cache_read_tokens": 700,
                    "cache_write_tokens": 150,
                    "cost_usd": 0.0035,
                }) + "\n"
            )

            # Get the path to token_report.py in the workspace
            script_path = Path(__file__).parent.parent / "token_report.py"

            # Invoke token_report.py with the temporary directory
            result = subprocess.run(
                ["python", str(script_path), "--tokens-dir", str(tmpdir_path)],
                capture_output=True,
                text=True,
                cwd=tmpdir_path,
            )

            # Assert exit code is 0
            error_msg = (
                f"Expected exit code 0, got {result.returncode}. "
                f"stderr: {result.stderr}"
            )
            assert result.returncode == 0, error_msg

            # Assert stdout contains a filename matching the pattern
            output = result.stdout.strip()
            pattern = r"token-report_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.html"
            assert re.search(pattern, output), (
                f"stdout does not match expected pattern. stdout: {output}"
            )

            # Assert the file was created in the output directory
            output_file = tmpdir_path / output
            assert output_file.exists(), f"Output file not found: {output_file}"

            # Read the HTML content
            html_content = output_file.read_text(encoding="utf-8")

            # Assert the HTML contains both agent names
            assert "designer" in html_content, (
                "HTML does not contain 'designer' agent name"
            )
            assert "agent" in html_content, (
                "HTML does not contain 'agent' agent name"
            )

            # Assert the HTML contains RAW_BUCKETS
            assert "RAW_BUCKETS" in html_content, (
                "HTML does not contain RAW_BUCKETS"
            )

            # Assert the HTML contains <!DOCTYPE html>
            assert "<!DOCTYPE html>" in html_content, (
                "HTML does not contain <!DOCTYPE html>"
            )

    def test_error_on_no_jsonl_files(self):
        """Test behavior when no .jsonl files are found.

        Verify:
        - Exit code is 1
        - stderr contains an error message
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Get the path to token_report.py in the workspace
            script_path = Path(__file__).parent.parent / "token_report.py"

            # Invoke token_report.py with an empty directory
            result = subprocess.run(
                ["python", str(script_path), "--tokens-dir", str(tmpdir_path)],
                capture_output=True,
                text=True,
                cwd=tmpdir_path,
            )

            # Assert exit code is 1
            assert result.returncode == 1, (
                f"Expected exit code 1, got {result.returncode}. "
                f"stdout: {result.stdout}, stderr: {result.stderr}"
            )

            # Assert stderr contains an error message
            assert "Error" in result.stderr or "no .jsonl files" in result.stderr, (
                f"stderr does not contain meaningful error message. "
                f"stderr: {result.stderr}"
            )
