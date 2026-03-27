# STORY-006: EPUB Assembly (`build_epub`)

**Index**: 6
**Attempts**: 1
**Design ref**: design/md-to-epub.md
**Depends on**: STORY-005

## Context
`build_epub` transforms a list of `Chapter` objects and the parsed CLI args into a fully configured `ebooklib` `EpubBook` object. This is the heart of the EPUB generation: it sets metadata, applies the default CSS, embeds images, constructs chapter HTML items, and wires up the spine and table of contents. The result is handed back to `main()` for writing to disk.

## Acceptance Criteria
- [ ] The function signature is exactly `build_epub(chapters: list[Chapter], args: argparse.Namespace) -> epub.EpubBook`
- [ ] Book title is set to `args.title` (guaranteed non-None by the time this is called)
- [ ] Book author is added via `book.add_author(args.author)`
- [ ] Book language is set to `args.language`
- [ ] Publisher is added to metadata only when `args.publisher` is not `None`
- [ ] A default CSS stylesheet is created as an `EpubItem` with `media_type='text/css'` and added to the book; it must contain at minimum: `body { font-family: serif; line-height: 1.6; margin: 1em; }` and basic styles for `h1`–`h3`, `p`, `code`, `pre`, and `img`
- [ ] Each `Chapter` becomes an `EpubHtml` item with a unique `file_name` (e.g. `chapterN.xhtml` where N is the 1-based index), `title` set to `chapter.title`, and content set to a complete XHTML document wrapping `chapter.html_body` (doctype, `<html>`, `<head>` with CSS link, `<body>`)
- [ ] Each image in `chapter.images` is added to the book as an `EpubImage` item with a unique `file_name` under `images/` (e.g. `images/<sanitised-src>`) and its media type inferred from the file extension (`.jpg`/`.jpeg` → `image/jpeg`, `.png` → `image/png`, `.gif` → `image/gif`, `.webp` → `image/webp`; unknown → `application/octet-stream`)
- [ ] The spine is set to `['nav'] + [all EpubHtml items in order]`
- [ ] A `toc` is built as a list of `epub.Link` objects (one per chapter, pointing to `chapterN.xhtml`)
- [ ] If `args.cover` is not `None`: read the image file bytes using `Pillow` (`Image.open`) to validate it is a real image (raises `PIL.UnidentifiedImageError` if not); then add it as the cover via `epub.set_cover(filename, bytes)` — use the original file extension for the cover filename
- [ ] The function returns the fully configured `EpubBook` without writing to disk

## Implementation Hints
- `ebooklib` XHTML chapter content must be a full XHTML document string, not just a fragment. Wrap with:
  ```python
  XHTML_TEMPLATE = """<?xml version='1.0' encoding='utf-8'?>
  <!DOCTYPE html>
  <html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>{title}</title><link rel="stylesheet" href="../style.css" type="text/css"/></head>
  <body>{body}</body>
  </html>"""
  ```
- `epub.EpubBook`, `epub.EpubHtml`, `epub.EpubImage`, `epub.EpubItem`, `epub.Link` are all in `ebooklib.epub`
- Use `book.add_item(epub.EpubNcx())` and `book.add_item(epub.EpubNav())` for EPUB3 navigation
- `book.spine` must include the string `'nav'` as its first element
- For image file names, sanitise `src` by replacing path separators and spaces: `src.replace('/', '_').replace('\\', '_').replace(' ', '_')`
- Pillow validation: `from PIL import Image, UnidentifiedImageError; Image.open(io.BytesIO(cover_bytes)).verify()` — use `io.BytesIO` to avoid a second disk read; catch `UnidentifiedImageError` and `Exception` broadly, print to stderr, and skip adding the cover rather than aborting

## Test Requirements
- `build_epub([chapter], args)` with a minimal chapter returns an `EpubBook` instance
- The returned book's title matches `args.title`
- The returned book's language matches `args.language`
- Publisher metadata is present when `args.publisher` is set and absent when it is `None`
- Chapter `file_name` for the first chapter is `"chapter1.xhtml"`
- All images from `chapter.images` are present as `EpubImage` items on the book
- CSS item with `media_type='text/css'` is present on the book
- With a valid JPEG cover file, the cover item is added without error
- With an invalid (corrupt) cover file, a warning is printed to stderr and the book is still returned (no exception raised)

---
<!-- Coding Agent appends timestamped failure notes below this line -->
