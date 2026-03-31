"""Tests for the Chart.js bundle caching functionality."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from token_report import get_chartjs_bundle


class TestChartjsCache:
    """Tests for the Chart.js bundle cache."""

    def test_cache_hit_no_network_request(self):
        """Test cache hit: cached file is read without network request.

        Verify:
        - If cache file exists, its content is returned immediately
        - No network request is made (urlopen is not called)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache_file = cache_dir / "chart.umd.min.js"

            # Write a fake JS bundle to the cache
            fake_js = "console.log('Chart.js mock');"
            cache_file.write_text(fake_js, encoding="utf-8")

            # Mock urlopen to raise if called
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.side_effect = Exception(
                    "Network request should not be made"
                )

                # Call the function
                result = get_chartjs_bundle(cache_dir)

                # Verify the cached content is returned
                assert result == fake_js

                # Verify urlopen was NOT called
                mock_urlopen.assert_not_called()

    def test_cache_miss_downloads_and_caches(self):
        """Test cache miss: bundle is downloaded and cached.

        Verify:
        - If cache file doesn't exist, bundle is downloaded from CDN
        - Downloaded content is cached to the correct location
        - Function returns the downloaded content as a string
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache_file = cache_dir / "chart.umd.min.js"

            # Fake bundle content
            fake_js = "var Chart = {}; Chart.version = '4.0.0';"
            fake_response = MagicMock()
            fake_response.read.return_value = fake_js.encode("utf-8")

            # Mock urlopen to return fake response
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.return_value = fake_response

                # Call the function
                result = get_chartjs_bundle(cache_dir)

                # Verify the downloaded content is returned
                assert result == fake_js

                # Verify cache file was created with correct content
                assert cache_file.exists()
                assert cache_file.read_text(encoding="utf-8") == fake_js

                # Verify urlopen was called with correct URL
                mock_urlopen.assert_called_once()
                args, kwargs = mock_urlopen.call_args
                assert "chart.js" in args[0]
                assert "cdn.jsdelivr.net" in args[0]

    def test_cache_directory_created_if_missing(self):
        """Test that cache directory is created if it doesn't exist.

        Verify:
        - Parent directories are created as needed
        - Cache file is created with correct content
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            cache_dir = base_dir / "nested" / "cache" / "dir"

            # Verify cache directory doesn't exist
            assert not cache_dir.exists()

            fake_js = "console.log('test');"
            fake_response = MagicMock()
            fake_response.read.return_value = fake_js.encode("utf-8")

            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.return_value = fake_response

                # Call the function
                get_chartjs_bundle(cache_dir)

                # Verify cache directory was created
                assert cache_dir.exists()

                # Verify cache file exists
                cache_file = cache_dir / "chart.umd.min.js"
                assert cache_file.exists()
