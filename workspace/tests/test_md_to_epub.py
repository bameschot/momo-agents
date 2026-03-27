"""
Test suite for md_to_epub.py
"""
import io
import sys
import zipfile

import pytest
from PIL import Image as PILImage
from ebooklib import epub

# Ensure workspace is on path for imports
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from md_to_epub import (
    Chapter,
    build_epub,
    collect_images,
    extract_chapter_title,
    main,
    md_file_to_chapter,
    parse_args,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_args(**kwargs):
    import argparse
    ns = argparse.Namespace(
        title="Test Book",
        author="Test Author",
        language="en",
        publisher=None,
        cover=None,
        output=None,
    )
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


def _make_png_bytes() -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (10, 10), color="red").save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# test_extract_chapter_title
# ---------------------------------------------------------------------------

class TestExtractChapterTitle:
    def test_h1_found(self):
        assert extract_chapter_title("# Hello World\n\nText.", "file.md") == "Hello World"

    def test_h1_not_found_stem_fallback(self):
        assert extract_chapter_title("## Sub\n\nText.", "path/to/my-file.md") == "my-file"

    def test_no_headings_stem_fallback(self):
        assert extract_chapter_title("Just text.", "chapter.md") == "chapter"

    def test_bold_inline_stripped(self):
        assert extract_chapter_title("# **Bold** Title", "f.md") == "Bold Title"

    def test_h1_not_on_first_line(self):
        text = "line1\nline2\nline3\n# My Title\nmore"
        assert extract_chapter_title(text, "f.md") == "My Title"

    def test_empty_string(self):
        assert extract_chapter_title("", "myfile.md") == "myfile"

    def test_only_first_h1_used(self):
        text = "# First\n\n# Second\n"
        assert extract_chapter_title(text, "f.md") == "First"


# ---------------------------------------------------------------------------
# test_collect_images
# ---------------------------------------------------------------------------

class TestCollectImages:
    def test_image_present(self, tmp_path):
        img = tmp_path / "logo.png"
        img.write_bytes(b"PNGDATA")
        result = collect_images('<img src="logo.png">', tmp_path)
        assert result == {"logo.png": b"PNGDATA"}

    def test_image_missing_warning(self, tmp_path):
        with pytest.warns(UserWarning):
            result = collect_images('<img src="missing.png">', tmp_path)
        assert result == {}

    def test_remote_url_skipped_no_warning(self, tmp_path):
        import warnings as _warnings
        with _warnings.catch_warnings(record=True) as w:
            _warnings.simplefilter("always")
            result = collect_images('<img src="https://example.com/img.png">', tmp_path)
        assert result == {}
        # No UserWarning about images should have been raised
        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 0

    def test_no_img_tags(self, tmp_path):
        result = collect_images("<p>No images here</p>", tmp_path)
        assert result == {}

    def test_mixed_present_and_missing(self, tmp_path):
        img = tmp_path / "logo.png"
        img.write_bytes(b"IMGBYTES")
        with pytest.warns(UserWarning):
            result = collect_images('<img src="logo.png"><img src="missing.png">', tmp_path)
        assert list(result.keys()) == ["logo.png"]

    def test_single_quotes(self, tmp_path):
        img = tmp_path / "logo.png"
        img.write_bytes(b"BYTES")
        result = collect_images("<img src='logo.png'>", tmp_path)
        assert result == {"logo.png": b"BYTES"}


# ---------------------------------------------------------------------------
# test_md_file_to_chapter
# ---------------------------------------------------------------------------

class TestMdFileToChapter:
    def test_basic_conversion(self, tmp_path):
        f = tmp_path / "chapter.md"
        f.write_text("# My Chapter\n\nHello world.\n", encoding="utf-8")
        ch = md_file_to_chapter(f)
        assert ch.title == "My Chapter"
        assert "Hello world" in ch.html_body
        assert ch.images == {}

    def test_no_h1_uses_stem(self, tmp_path):
        f = tmp_path / "my-stem.md"
        f.write_text("## Sub\n\nText.\n", encoding="utf-8")
        ch = md_file_to_chapter(f)
        assert ch.title == "my-stem"

    def test_table_rendering(self, tmp_path):
        f = tmp_path / "table.md"
        f.write_text("| A | B |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8")
        ch = md_file_to_chapter(f)
        assert "<table>" in ch.html_body

    def test_fenced_code_rendering(self, tmp_path):
        f = tmp_path / "code.md"
        f.write_text("```python\nprint('hi')\n```\n", encoding="utf-8")
        ch = md_file_to_chapter(f)
        assert "<code" in ch.html_body or "<pre" in ch.html_body

    def test_missing_image_warning(self, tmp_path):
        f = tmp_path / "imgs.md"
        f.write_text("# Title\n\n![alt](nope.png)\n", encoding="utf-8")
        with pytest.warns(UserWarning):
            ch = md_file_to_chapter(f)
        assert ch.images == {}

    def test_present_image_collected(self, tmp_path):
        img = tmp_path / "img.png"
        img.write_bytes(b"IMGDATA")
        f = tmp_path / "chapter.md"
        f.write_text("# Title\n\n![alt](img.png)\n", encoding="utf-8")
        ch = md_file_to_chapter(f)
        assert "img.png" in ch.images


# ---------------------------------------------------------------------------
# test_build_epub
# ---------------------------------------------------------------------------

class TestBuildEpub:
    def test_returns_epub_book(self):
        ch = Chapter(title="Ch1", html_body="<p>Hello</p>", images={})
        book = build_epub([ch], _make_args())
        assert isinstance(book, epub.EpubBook)

    def test_title_and_language_set(self):
        ch = Chapter(title="Ch1", html_body="<p>Hello</p>", images={})
        book = build_epub([ch], _make_args(title="My Title", language="fr"))
        assert book.title == "My Title"
        assert book.language == "fr"

    def test_author_set(self):
        ch = Chapter(title="Ch1", html_body="<p>Hello</p>", images={})
        book = build_epub([ch], _make_args(author="Jane Doe"))
        authors = book.get_metadata("DC", "creator")
        assert any("Jane Doe" in str(a) for a in authors)

    def test_publisher_present(self):
        ch = Chapter(title="Ch1", html_body="<p>Hello</p>", images={})
        book = build_epub([ch], _make_args(publisher="Acme Press"))
        pub = book.get_metadata("DC", "publisher")
        assert len(pub) == 1
        assert "Acme Press" in str(pub[0])

    def test_publisher_absent(self):
        ch = Chapter(title="Ch1", html_body="<p>Hello</p>", images={})
        book = build_epub([ch], _make_args(publisher=None))
        pub = book.get_metadata("DC", "publisher")
        assert pub == []

    def test_css_item_present(self):
        ch = Chapter(title="Ch1", html_body="<p>Hello</p>", images={})
        book = build_epub([ch], _make_args())
        css_items = [
            item for item in book.get_items()
            if getattr(item, "media_type", "") == "text/css"
        ]
        assert len(css_items) == 1

    def test_chapter_item_present(self):
        ch = Chapter(title="Ch1", html_body="<p>Hello</p>", images={})
        book = build_epub([ch], _make_args())
        items = {item.file_name: item for item in book.get_items()}
        assert "chapter1.xhtml" in items

    def test_image_items_present(self):
        ch = Chapter(title="Ch1", html_body="<img src='logo.png'/>", images={"logo.png": b"BYTES"})
        book = build_epub([ch], _make_args())
        img_items = {
            item.file_name: item for item in book.get_items()
            if "image" in getattr(item, "media_type", "")
        }
        assert "images/logo.png" in img_items

    def test_valid_cover_added(self, tmp_path):
        cover = tmp_path / "cover.png"
        cover.write_bytes(_make_png_bytes())
        ch = Chapter(title="Ch1", html_body="<p>Hello</p>", images={})
        # Should not raise
        book = build_epub([ch], _make_args(cover=str(cover)))
        assert isinstance(book, epub.EpubBook)

    def test_invalid_cover_no_exception(self, tmp_path, capsys):
        cover = tmp_path / "bad.jpg"
        cover.write_bytes(b"NOT_AN_IMAGE")
        ch = Chapter(title="Ch1", html_body="<p>Hello</p>", images={})
        book = build_epub([ch], _make_args(cover=str(cover)))
        assert isinstance(book, epub.EpubBook)
        captured = capsys.readouterr()
        assert "Warning" in captured.err or "warning" in captured.err.lower()


# ---------------------------------------------------------------------------
# test_parse_args
# ---------------------------------------------------------------------------

class TestParseArgs:
    def test_defaults(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["md_to_epub.py", "a.md"])
        args = parse_args()
        assert args.files == ["a.md"]
        assert args.title is None
        assert args.author == "Unknown"
        assert args.language == "en"
        assert args.publisher is None
        assert args.cover is None
        assert args.output is None

    def test_all_flags(self, monkeypatch):
        monkeypatch.setattr(
            sys, "argv",
            ["md_to_epub.py", "a.md", "--title", "T", "--author", "A",
             "--language", "fr", "--publisher", "P", "--cover", "c.jpg",
             "--output", "out.epub"],
        )
        args = parse_args()
        assert args.title == "T"
        assert args.author == "A"
        assert args.language == "fr"
        assert args.publisher == "P"
        assert args.cover == "c.jpg"
        assert args.output == "out.epub"

    def test_missing_positional_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["md_to_epub.py"])
        with pytest.raises(SystemExit) as exc:
            parse_args()
        assert exc.value.code != 0


# ---------------------------------------------------------------------------
# test_main_integration
# ---------------------------------------------------------------------------

class TestMainIntegration:
    def test_end_to_end_single_file(self, tmp_path, monkeypatch, capsys):
        f = tmp_path / "chapter.md"
        f.write_text("# Hello\n\nContent.\n", encoding="utf-8")
        out = tmp_path / "output.epub"
        monkeypatch.setattr(sys, "argv", ["md_to_epub.py", str(f), "--output", str(out)])
        main()
        assert out.exists()
        assert zipfile.is_zipfile(str(out))
        captured = capsys.readouterr()
        assert "EPUB written to" in captured.out

    def test_end_to_end_multi_file(self, tmp_path, monkeypatch):
        f1 = tmp_path / "ch1.md"
        f2 = tmp_path / "ch2.md"
        f1.write_text("# Chapter One\n\nFirst.\n", encoding="utf-8")
        f2.write_text("# Chapter Two\n\nSecond.\n", encoding="utf-8")
        out = tmp_path / "book.epub"
        monkeypatch.setattr(
            sys, "argv",
            ["md_to_epub.py", str(f1), str(f2), "--output", str(out), "--title", "Multi"],
        )
        main()
        assert out.exists()
        assert zipfile.is_zipfile(str(out))

    def test_missing_input_file_exits_1(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["md_to_epub.py", str(tmp_path / "nope.md")])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_output_flag_honored(self, tmp_path, monkeypatch):
        f = tmp_path / "ch.md"
        f.write_text("# Test\n\nText.\n", encoding="utf-8")
        out = tmp_path / "custom.epub"
        monkeypatch.setattr(
            sys, "argv", ["md_to_epub.py", str(f), "--output", str(out)]
        )
        main()
        assert out.exists()

    def test_default_output_derived_from_title(self, tmp_path, monkeypatch):
        f = tmp_path / "my-story.md"
        f.write_text("# Story\n\nContent.\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["md_to_epub.py", str(f), "--title", "My Novel"])
        monkeypatch.chdir(tmp_path)
        main()
        expected = tmp_path / "my-novel.epub"
        assert expected.exists(), f"Expected {expected}"

    def test_title_derived_from_filename_stem(self, tmp_path, monkeypatch, capsys):
        f = tmp_path / "great-adventure.md"
        f.write_text("## Sub\n\nContent.\n", encoding="utf-8")
        out = tmp_path / "out.epub"
        monkeypatch.setattr(
            sys, "argv", ["md_to_epub.py", str(f), "--output", str(out)]
        )
        main()
        captured = capsys.readouterr()
        assert "EPUB written to" in captured.out
