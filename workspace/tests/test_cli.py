"""Tests for the CLI interface."""

import re
import subprocess
import tempfile
from pathlib import Path


class TestCLI:
    """Tests for the CLI interface."""

    def test_happy_path_with_valid_directory(self):
        """Test invoking token_report.py with valid tokens directory.

        Verify:
        - Exit code is 0
        - stdout contains a filename matching token-report_YYYY-MM-DD_HH-MM-SS.html
        - Output file is created in the current directory
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create at least one .jsonl file
            jsonl_file = tmpdir_path / "test.jsonl"
            jsonl_file.write_text('{"ts": "2026-03-30T12:00:00Z"}\n')

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

    def test_error_on_missing_tokens_directory(self):
        """Test invoking token_report.py with nonexistent directory.

        Verify:
        - Exit code is 1
        - stderr contains a meaningful error message
        """
        nonexistent_path = "/nonexistent/path/to/tokens"

        # Get the path to token_report.py in the workspace
        script_path = Path(__file__).parent.parent / "token_report.py"

        result = subprocess.run(
            ["python", str(script_path), "--tokens-dir", nonexistent_path],
            capture_output=True,
            text=True,
        )

        # Assert exit code is 1
        assert result.returncode == 1, (
            f"Expected exit code 1, got {result.returncode}. stderr: {result.stderr}"
        )

        # Assert stderr contains an error message
        assert "Error" in result.stderr or "not found" in result.stderr, (
            f"stderr does not contain meaningful error message. stderr: {result.stderr}"
        )
