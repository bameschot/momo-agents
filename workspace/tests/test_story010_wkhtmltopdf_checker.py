"""
Tests for STORY-010: WkhtmltopdfChecker — Dependency Validator

Covers check_wkhtmltopdf() with mocked shutil.which, and verifies that
main() calls check_wkhtmltopdf() before any file I/O.
"""
from __future__ import annotations

import sys
import os
from io import StringIO
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from md2pdf import check_wkhtmltopdf, main


# ---------------------------------------------------------------------------
# check_wkhtmltopdf() — binary found
# ---------------------------------------------------------------------------


def test_check_wkhtmltopdf_found(capsys):
    """When wkhtmltopdf is found, returns None and nothing is written to stderr."""
    with patch("shutil.which", return_value="/usr/local/bin/wkhtmltopdf"):
        result = check_wkhtmltopdf()
    assert result is None
    captured = capsys.readouterr()
    assert captured.err == ""


# ---------------------------------------------------------------------------
# check_wkhtmltopdf() — binary not found
# ---------------------------------------------------------------------------


def test_check_wkhtmltopdf_not_found_raises_system_exit(capsys):
    """When wkhtmltopdf is missing, SystemExit with code 1 is raised."""
    with patch("shutil.which", return_value=None):
        with pytest.raises(SystemExit) as exc_info:
            check_wkhtmltopdf()
    assert exc_info.value.code == 1


def test_check_wkhtmltopdf_not_found_stderr_contains_wkhtmltopdf(capsys):
    """stderr message mentions 'wkhtmltopdf'."""
    with patch("shutil.which", return_value=None):
        with pytest.raises(SystemExit):
            check_wkhtmltopdf()
    captured = capsys.readouterr()
    assert "wkhtmltopdf" in captured.err


def test_check_wkhtmltopdf_not_found_stderr_contains_brew(capsys):
    """stderr message includes macOS install instruction with 'brew'."""
    with patch("shutil.which", return_value=None):
        with pytest.raises(SystemExit):
            check_wkhtmltopdf()
    captured = capsys.readouterr()
    assert "brew" in captured.err


def test_check_wkhtmltopdf_not_found_stderr_contains_apt(capsys):
    """stderr message includes Linux install instruction with 'apt-get'."""
    with patch("shutil.which", return_value=None):
        with pytest.raises(SystemExit):
            check_wkhtmltopdf()
    captured = capsys.readouterr()
    assert "apt-get" in captured.err


def test_check_wkhtmltopdf_not_found_stderr_contains_download_url(capsys):
    """stderr message references wkhtmltopdf.org."""
    with patch("shutil.which", return_value=None):
        with pytest.raises(SystemExit):
            check_wkhtmltopdf()
    captured = capsys.readouterr()
    assert "wkhtmltopdf.org" in captured.err


def test_check_wkhtmltopdf_which_called_with_correct_name():
    """shutil.which is called with exactly 'wkhtmltopdf'."""
    with patch("shutil.which", return_value="/usr/bin/wkhtmltopdf") as mock_which:
        check_wkhtmltopdf()
    mock_which.assert_called_once_with("wkhtmltopdf")


# ---------------------------------------------------------------------------
# main() calls check_wkhtmltopdf() before any file I/O
# ---------------------------------------------------------------------------


def test_main_calls_check_wkhtmltopdf_before_file_read():
    """main() must call check_wkhtmltopdf() first — even if the input file doesn't exist.

    When wkhtmltopdf is missing, SystemExit(1) should be raised regardless
    of whether the input file is valid.
    """
    with patch("shutil.which", return_value=None):
        with pytest.raises(SystemExit) as exc_info:
            # Pass a clearly nonexistent file — check_wkhtmltopdf should fire first.
            sys.argv = ["md2pdf", "nonexistent_file_that_does_not_exist.md"]
            main()
    assert exc_info.value.code == 1
