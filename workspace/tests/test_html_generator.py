"""Tests for HTML generation and Chart.js bundle fetching."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
from token_report import get_chartjs_source


def test_get_chartjs_source_from_cache() -> None:
    """When cache exists, get_chartjs_source returns cache without network call."""
    dummy_js = "/*! Chart.js v4.0.0 */\n!function(){console.log('test');}();"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        cache_file = tmppath / "chart.umd.min.js"
        cache_file.write_text(dummy_js, encoding="utf-8")

        # Monkeypatch CHARTJS_CACHE_PATH to point to our temp cache
        with patch("token_report.CHARTJS_CACHE_PATH", cache_file):
            # Also monkeypatch urllib.request.urlopen to raise if called
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.side_effect = RuntimeError("Network call should not happen!")

                result = get_chartjs_source()

                # Verify we got the cache contents
                assert result == dummy_js
                # Verify urlopen was not called
                mock_urlopen.assert_not_called()


def test_get_chartjs_source_caches_on_miss() -> None:
    """When cache is missing, download is stored and returned."""
    dummy_js = "/*! Chart.js v4.0.0 */\n!function(){console.log('test');}();"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        cache_dir = tmppath / "cache"
        cache_file = cache_dir / "chart.umd.min.js"

        # Mock the download response
        mock_response = MagicMock()
        mock_response.read.return_value = dummy_js.encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None

        with patch("token_report.CHARTJS_CACHE_PATH", cache_file):
            with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
                result = get_chartjs_source()

                # Verify we got the source
                assert result == dummy_js
                # Verify urlopen was called
                mock_urlopen.assert_called_once()
                # Verify cache was created
                assert cache_file.exists()
                assert cache_file.read_text(encoding="utf-8") == dummy_js


def test_get_chartjs_source_returns_nonempty() -> None:
    """Returned source is non-empty and starts with valid JS preamble."""
    dummy_js = "/*! Chart.js */\nvar Chart = {};"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        cache_file = tmppath / "chart.umd.min.js"
        cache_file.write_text(dummy_js, encoding="utf-8")

        with patch("token_report.CHARTJS_CACHE_PATH", cache_file):
            with patch("urllib.request.urlopen"):
                result = get_chartjs_source()

                # Verify non-empty
                assert len(result) > 0
                # Verify starts with valid preamble
                stripped = result.strip()
                valid_starts = ("/*", "//", "!", "(")
                assert any(stripped.startswith(start) for start in valid_starts)
