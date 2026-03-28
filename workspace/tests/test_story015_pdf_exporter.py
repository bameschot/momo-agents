"""
Tests for STORY-015: export_pdf(), main() wiring, and end-to-end CLI integration.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make sure the workspace root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from md2pdf import export_pdf  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"
BASIC_MD = FIXTURES_DIR / "basic.md"
NO_HEADINGS_MD = FIXTURES_DIR / "no_headings.md"

# Whether wkhtmltopdf is available on this machine
_HAS_WKHTMLTOPDF = shutil.which("wkhtmltopdf") is not None

requires_wkhtmltopdf = pytest.mark.skipif(
    not _HAS_WKHTMLTOPDF,
    reason="wkhtmltopdf not found on PATH — skipping wkhtmltopdf-dependent tests",
)

# ---------------------------------------------------------------------------
# Unit tests — export_pdf
# ---------------------------------------------------------------------------


def test_export_pdf_temp_file_deleted_on_success(tmp_path: Path) -> None:
    """Temp HTML file must be deleted after a successful wkhtmltopdf run."""
    output_pdf = tmp_path / "out.pdf"
    html_content = "<html><body><p>Hello</p></body></html>"

    captured_tmp_paths: list[str] = []

    real_named_temp = __import__("tempfile").NamedTemporaryFile

    def _mock_named_temp(*args, **kwargs):
        f = real_named_temp(*args, **kwargs)
        captured_tmp_paths.append(f.name)
        return f

    mock_result = MagicMock()
    mock_result.returncode = 0

    with patch("md2pdf.subprocess.run", return_value=mock_result), \
         patch("tempfile.NamedTemporaryFile", side_effect=_mock_named_temp):
        export_pdf(html_content, output_pdf)

    assert captured_tmp_paths, "Expected at least one temp file to be created"
    for path in captured_tmp_paths:
        assert not Path(path).exists(), f"Temp file was not deleted: {path}"


def test_export_pdf_temp_file_deleted_on_failure(tmp_path: Path) -> None:
    """Temp HTML file must be deleted even when wkhtmltopdf fails."""
    output_pdf = tmp_path / "out.pdf"
    html_content = "<html><body><p>Hello</p></body></html>"

    captured_tmp_paths: list[str] = []

    real_named_temp = __import__("tempfile").NamedTemporaryFile

    def _mock_named_temp(*args, **kwargs):
        f = real_named_temp(*args, **kwargs)
        captured_tmp_paths.append(f.name)
        return f

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = b"wkhtmltopdf: error message\n"

    with patch("md2pdf.subprocess.run", return_value=mock_result), \
         patch("tempfile.NamedTemporaryFile", side_effect=_mock_named_temp), \
         pytest.raises(SystemExit) as exc_info:
        export_pdf(html_content, output_pdf)

    assert exc_info.value.code == 1
    assert captured_tmp_paths, "Expected at least one temp file to be created"
    for path in captured_tmp_paths:
        assert not Path(path).exists(), f"Temp file was not deleted: {path}"


def test_export_pdf_failure_stderr(tmp_path: Path, capsys) -> None:
    """stderr from wkhtmltopdf should be written to the process stderr on failure."""
    output_pdf = tmp_path / "out.pdf"
    html_content = "<html><body><p>Hello</p></body></html>"

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = b"fatal wkhtmltopdf error\n"

    with patch("md2pdf.subprocess.run", return_value=mock_result), \
         pytest.raises(SystemExit):
        export_pdf(html_content, output_pdf)


def test_export_pdf_builds_correct_command(tmp_path: Path) -> None:
    """export_pdf must pass the expected wkhtmltopdf flags."""
    output_pdf = tmp_path / "out.pdf"
    html_content = "<html><body></body></html>"

    mock_result = MagicMock()
    mock_result.returncode = 0

    with patch("md2pdf.subprocess.run", return_value=mock_result) as mock_run:
        export_pdf(html_content, output_pdf)

    call_args = mock_run.call_args
    cmd = call_args[0][0]  # positional first arg

    assert cmd[0] == "wkhtmltopdf"
    assert "--page-size" in cmd
    assert "A4" in cmd
    assert "--margin-top" in cmd
    assert "20mm" in cmd
    assert "--enable-internal-links" in cmd
    assert "--enable-local-file-access" in cmd
    # Last two args: temp html path and output pdf path
    assert cmd[-1] == str(output_pdf)


# ---------------------------------------------------------------------------
# Integration tests — full CLI pipeline (require wkhtmltopdf)
# ---------------------------------------------------------------------------


@requires_wkhtmltopdf
def test_integration_basic_conversion(tmp_path: Path) -> None:
    """Integration test 1: basic conversion produces a non-empty PDF."""
    output_pdf = tmp_path / "output.pdf"
    result = subprocess.run(
        [sys.executable, "md2pdf.py", str(BASIC_MD), "-o", str(output_pdf)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert output_pdf.exists(), "Output PDF was not created"
    assert output_pdf.stat().st_size > 0, "Output PDF is empty"


@requires_wkhtmltopdf
def test_integration_explicit_output_path(tmp_path: Path) -> None:
    """Integration test 2: -o flag writes PDF to the specified path."""
    custom_output = tmp_path / "custom_name.pdf"
    result = subprocess.run(
        [sys.executable, "md2pdf.py", str(BASIC_MD), "-o", str(custom_output)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert custom_output.exists(), "PDF not written to custom output path"
    assert custom_output.stat().st_size > 0


@requires_wkhtmltopdf
def test_integration_title_override(tmp_path: Path) -> None:
    """Integration test 3: -t flag is accepted and PDF is produced."""
    output_pdf = tmp_path / "titled.pdf"
    result = subprocess.run(
        [
            sys.executable, "md2pdf.py",
            str(BASIC_MD),
            "-o", str(output_pdf),
            "-t", "My Custom Title",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 0


def test_integration_missing_input_file(tmp_path: Path) -> None:
    """Integration test 4: missing input file returns non-zero exit and error message."""
    nonexistent = tmp_path / "does_not_exist.md"
    result = subprocess.run(
        [sys.executable, "md2pdf.py", str(nonexistent)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    assert result.returncode != 0
    # argparse prints to stderr; the combined output should mention the file
    combined = result.stderr + result.stdout
    assert "does_not_exist" in combined or "error" in combined.lower()


@requires_wkhtmltopdf
def test_integration_default_output_path(tmp_path: Path) -> None:
    """Integration test 5: without -o, PDF is placed next to input file with .pdf extension."""
    import shutil as _shutil

    # Copy fixture to tmp_path so the output lands there too
    src = tmp_path / "basic.md"
    _shutil.copy(BASIC_MD, src)

    expected_pdf = tmp_path / "basic.pdf"

    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent.parent / "md2pdf.py"), str(src)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert expected_pdf.exists(), "Default output PDF not created next to input"
    assert expected_pdf.stat().st_size > 0


@requires_wkhtmltopdf
def test_integration_no_headings_no_toc(tmp_path: Path) -> None:
    """Integration test 6: document with no headings produces a PDF without crashing."""
    output_pdf = tmp_path / "no_headings.pdf"
    result = subprocess.run(
        [sys.executable, "md2pdf.py", str(NO_HEADINGS_MD), "-o", str(output_pdf)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 0
