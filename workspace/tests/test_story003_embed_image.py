"""
Tests for STORY-003: Image Embedder

Tests cover embed_image() behaviour:
  - local PNG file → data:image/png;base64,... URI
  - local JPEG file → data:image/jpeg;base64,... URI
  - local GIF, WebP, SVG files
  - HTTP/HTTPS URLs returned unchanged
  - missing local file → warning to stderr + original src returned
  - unknown/unsupported extension → warning to stderr + original src returned
  - no network access required
  - no exceptions raised for any supported input
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from md2html import embed_image  # noqa: E402

# ---------------------------------------------------------------------------
# Minimal valid image bytes for each format (used as fixture data)
# ---------------------------------------------------------------------------

# A 1×1 red pixel PNG (minimal valid PNG)
_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)

# Minimal JPEG SOI + EOI markers
_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"

# Minimal GIF89a header
_GIF_BYTES = b"GIF89a\x01\x00\x01\x00\x00\x00\x00!"

# Minimal WebP RIFF header
_WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8L"

# Minimal SVG
_SVG_BYTES = b'<svg xmlns="http://www.w3.org/2000/svg"/>'


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_image(tmp_path: Path, name: str, content: bytes) -> Path:
    """Write *content* to *tmp_path/name* and return the Path."""
    p = tmp_path / name
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------------------
# Tests: local image embedding
# ---------------------------------------------------------------------------


class TestLocalImages:
    def test_png_returns_data_uri(self, tmp_path: Path) -> None:
        _make_image(tmp_path, "sample.png", _PNG_BYTES)
        result = embed_image("sample.png", tmp_path)
        expected_b64 = base64.b64encode(_PNG_BYTES).decode("ascii")
        assert result == f"data:image/png;base64,{expected_b64}"

    def test_png_uri_prefix(self, tmp_path: Path) -> None:
        _make_image(tmp_path, "sample.png", _PNG_BYTES)
        result = embed_image("sample.png", tmp_path)
        assert result.startswith("data:image/png;base64,")

    def test_jpg_extension(self, tmp_path: Path) -> None:
        _make_image(tmp_path, "photo.jpg", _JPEG_BYTES)
        result = embed_image("photo.jpg", tmp_path)
        assert result.startswith("data:image/jpeg;base64,")

    def test_jpeg_extension(self, tmp_path: Path) -> None:
        _make_image(tmp_path, "photo.jpeg", _JPEG_BYTES)
        result = embed_image("photo.jpeg", tmp_path)
        assert result.startswith("data:image/jpeg;base64,")

    def test_gif_extension(self, tmp_path: Path) -> None:
        _make_image(tmp_path, "anim.gif", _GIF_BYTES)
        result = embed_image("anim.gif", tmp_path)
        assert result.startswith("data:image/gif;base64,")

    def test_webp_extension(self, tmp_path: Path) -> None:
        _make_image(tmp_path, "pic.webp", _WEBP_BYTES)
        result = embed_image("pic.webp", tmp_path)
        assert result.startswith("data:image/webp;base64,")

    def test_svg_extension(self, tmp_path: Path) -> None:
        _make_image(tmp_path, "icon.svg", _SVG_BYTES)
        result = embed_image("icon.svg", tmp_path)
        assert result.startswith("data:image/svg+xml;base64,")

    def test_case_insensitive_extension(self, tmp_path: Path) -> None:
        """Extension matching should be case-insensitive (.PNG, .JPG, etc.)."""
        _make_image(tmp_path, "photo.PNG", _PNG_BYTES)
        result = embed_image("photo.PNG", tmp_path)
        assert result.startswith("data:image/png;base64,")

    def test_data_uri_content_matches_file(self, tmp_path: Path) -> None:
        """The base64 payload must round-trip back to the original bytes."""
        _make_image(tmp_path, "sample.png", _PNG_BYTES)
        result = embed_image("sample.png", tmp_path)
        _, b64_part = result.split(",", 1)
        assert base64.b64decode(b64_part) == _PNG_BYTES

    def test_subdirectory_resolution(self, tmp_path: Path) -> None:
        """Images in a subdirectory should be resolved correctly."""
        sub = tmp_path / "assets"
        sub.mkdir()
        _make_image(sub, "logo.png", _PNG_BYTES)
        result = embed_image("assets/logo.png", tmp_path)
        assert result.startswith("data:image/png;base64,")


# ---------------------------------------------------------------------------
# Tests: HTTP/HTTPS URLs
# ---------------------------------------------------------------------------


class TestRemoteUrls:
    def test_http_url_returned_unchanged(self, tmp_path: Path) -> None:
        url = "http://example.com/image.png"
        assert embed_image(url, tmp_path) == url

    def test_https_url_returned_unchanged(self, tmp_path: Path) -> None:
        url = "https://example.com/image.png"
        assert embed_image(url, tmp_path) == url

    def test_https_url_with_query_string(self, tmp_path: Path) -> None:
        url = "https://cdn.example.com/img.jpg?v=123"
        assert embed_image(url, tmp_path) == url


# ---------------------------------------------------------------------------
# Tests: missing files → warning + original src
# ---------------------------------------------------------------------------


class TestMissingFile:
    def test_missing_file_returns_original_src(self, tmp_path: Path) -> None:
        result = embed_image("nonexistent.png", tmp_path)
        assert result == "nonexistent.png"

    def test_missing_file_prints_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        embed_image("nonexistent.png", tmp_path)
        captured = capsys.readouterr()
        assert "Warning: image not found: nonexistent.png" in captured.err

    def test_missing_file_does_not_raise(self, tmp_path: Path) -> None:
        # Must not raise any exception.
        embed_image("no_such_file.png", tmp_path)


# ---------------------------------------------------------------------------
# Tests: unsupported/unknown extensions → warning + original src
# ---------------------------------------------------------------------------


class TestUnsupportedExtension:
    def test_bmp_returns_original_src(self, tmp_path: Path) -> None:
        _make_image(tmp_path, "image.bmp", b"BM")
        result = embed_image("image.bmp", tmp_path)
        assert result == "image.bmp"

    def test_bmp_prints_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_image(tmp_path, "image.bmp", b"BM")
        embed_image("image.bmp", tmp_path)
        captured = capsys.readouterr()
        assert "Warning: image not found: image.bmp" in captured.err

    def test_tiff_returns_original_src(self, tmp_path: Path) -> None:
        _make_image(tmp_path, "scan.tiff", b"\x49\x49")
        result = embed_image("scan.tiff", tmp_path)
        assert result == "scan.tiff"

    def test_no_extension_returns_original_src(self, tmp_path: Path) -> None:
        _make_image(tmp_path, "noext", b"data")
        result = embed_image("noext", tmp_path)
        assert result == "noext"

    def test_unsupported_does_not_raise(self, tmp_path: Path) -> None:
        embed_image("image.bmp", tmp_path)


# ---------------------------------------------------------------------------
# Tests: no exceptions under any condition
# ---------------------------------------------------------------------------


class TestNoExceptions:
    def test_empty_src(self, tmp_path: Path) -> None:
        embed_image("", tmp_path)

    def test_absolute_nonexistent_path(self, tmp_path: Path) -> None:
        embed_image("/totally/nonexistent/image.png", tmp_path)
