import argparse
import io
import re
import sys
import warnings
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

import markdown
import ebooklib
from ebooklib import epub
from PIL import Image, UnidentifiedImageError


@dataclass
class Chapter:
    title: str
    html_body: str
    images: dict[str, bytes]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert one or more Markdown files into an EPUB e-book."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more Markdown (.md) files to include as chapters.",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Title of the EPUB (defaults to the stem of the first input file).",
    )
    parser.add_argument(
        "--author",
        default="Unknown",
        help="Author of the EPUB (default: Unknown).",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="BCP-47 language code for the EPUB (default: en).",
    )
    parser.add_argument(
        "--publisher",
        default=None,
        help="Publisher metadata for the EPUB (omitted when not supplied).",
    )
    parser.add_argument(
        "--cover",
        default=None,
        help="Path to a cover image file.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for the generated EPUB (defaults to <title>.epub).",
    )
    return parser.parse_args()


def extract_chapter_title(md_text: str, filename: str) -> str:
    match = re.search(r'^#\s+(.+)', md_text, re.MULTILINE)
    if match:
        heading_text = match.group(1)
        return re.sub(r'[*_`]', '', heading_text).strip()
    return Path(filename).stem


def collect_images(html: str, source_dir: Path) -> dict[str, bytes]:
    srcs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
    result: dict[str, bytes] = {}
    for src in srcs:
        if src.startswith(('http://', 'https://', 'data:')):
            continue
        img_path = (source_dir / src).resolve()
        try:
            result[src] = img_path.read_bytes()
        except (FileNotFoundError, OSError):
            warnings.warn(f"Image not found or unreadable: {src}", UserWarning)
    return result


def md_file_to_chapter(md_path: Path) -> Chapter:
    md_text = md_path.read_text(encoding='utf-8')
    title = extract_chapter_title(md_text, str(md_path))
    html = markdown.markdown(md_text, extensions=['extra', 'tables'])
    images = collect_images(html, md_path.parent)
    return Chapter(title=title, html_body=html, images=images)


_XHTML_TEMPLATE = """<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{title}</title><link rel="stylesheet" href="../style.css" type="text/css"/></head>
<body>{body}</body>
</html>"""

_DEFAULT_CSS = """body { font-family: serif; line-height: 1.6; margin: 1em; }
h1 { font-size: 2em; margin-top: 1em; }
h2 { font-size: 1.5em; margin-top: 0.8em; }
h3 { font-size: 1.2em; margin-top: 0.6em; }
p { margin: 0.5em 0; }
code { font-family: monospace; background: #f4f4f4; padding: 0.1em 0.3em; }
pre { font-family: monospace; background: #f4f4f4; padding: 1em; overflow-x: auto; }
img { max-width: 100%; height: auto; }
"""

_MIME_MAP = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
}


def _image_mime(src: str) -> str:
    ext = Path(src).suffix.lower()
    return _MIME_MAP.get(ext, 'application/octet-stream')


def build_epub(chapters: list[Chapter], args: argparse.Namespace) -> epub.EpubBook:
    book = epub.EpubBook()
    book.set_title(args.title)
    book.add_author(args.author)
    book.set_language(args.language)
    if args.publisher is not None:
        book.add_metadata('DC', 'publisher', args.publisher)

    # Default CSS
    css_item = epub.EpubItem(
        uid='style',
        file_name='style.css',
        media_type='text/css',
        content=_DEFAULT_CSS.encode('utf-8'),
    )
    book.add_item(css_item)

    # Cover image
    if args.cover is not None:
        try:
            cover_path = Path(args.cover)
            cover_bytes = cover_path.read_bytes()
            Image.open(io.BytesIO(cover_bytes)).verify()
            cover_filename = 'cover' + cover_path.suffix
            book.set_cover(cover_filename, cover_bytes)
        except (UnidentifiedImageError, Exception) as exc:
            print(f"Warning: could not add cover image: {exc}", file=sys.stderr)

    # Build chapter items
    epub_chapters = []
    toc = []
    for i, chapter in enumerate(chapters, start=1):
        chapter_filename = f'chapter{i}.xhtml'
        content = _XHTML_TEMPLATE.format(title=chapter.title, body=chapter.html_body)
        epub_ch = epub.EpubHtml(
            title=chapter.title,
            file_name=chapter_filename,
            lang=args.language,
        )
        epub_ch.content = content.encode('utf-8')
        epub_ch.add_item(css_item)
        book.add_item(epub_ch)
        epub_chapters.append(epub_ch)
        toc.append(epub.Link(chapter_filename, chapter.title, f'chapter{i}'))

        # Embed images
        for src, img_bytes in chapter.images.items():
            sanitised = src.replace('/', '_').replace('\\', '_').replace(' ', '_')
            img_item = epub.EpubImage(
                uid=sanitised,
                file_name=f'images/{sanitised}',
                media_type=_image_mime(src),
                content=img_bytes,
            )
            book.add_item(img_item)

    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav'] + epub_chapters

    return book


def main() -> None:
    args = parse_args()


if __name__ == "__main__":
    main()
