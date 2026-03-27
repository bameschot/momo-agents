# STORY-001: Project Scaffold & Chapter Dataclass

**Index**: 1
**Attempts**: 1
**Design ref**: design/md-to-epub.md
**Depends on**: none

## Context
This is the foundation story. It creates the two project files (`md_to_epub.py` and `requirements.txt`) in a state that is importable and runnable (no-op), establishing the skeleton that every subsequent story builds on. No logic is implemented here beyond the data model and empty stubs.

## Acceptance Criteria
- [ ] `requirements.txt` exists at the project root and declares exactly three dependencies: `markdown>=3.6`, `ebooklib>=0.18`, `Pillow>=10.0`
- [ ] `md_to_epub.py` exists at the project root
- [ ] `md_to_epub.py` imports all runtime dependencies (`argparse`, `dataclasses`, `pathlib`, `warnings`, `sys`, `re`, `html.parser`, `markdown`, `ebooklib`, `PIL`) at the top of the file
- [ ] The `Chapter` dataclass is defined with fields `title: str`, `html_body: str`, and `images: dict[str, bytes]`
- [ ] Empty stub functions exist for `parse_args`, `extract_chapter_title`, `collect_images`, `md_file_to_chapter`, `build_epub`, and `main`
- [ ] The file ends with a standard `if __name__ == "__main__": main()` guard
- [ ] Running `python md_to_epub.py` completes without error (stubs may simply `pass` or `return None`)
- [ ] `pip install -r requirements.txt` succeeds on Python 3.11+

## Implementation Hints
- Use `@dataclass` from the `dataclasses` standard-library module for `Chapter`
- Stub functions can use `...` or `pass` as their body — they just need to exist with the correct signatures so later stories can fill them in:
  - `def parse_args() -> argparse.Namespace`
  - `def extract_chapter_title(md_text: str, filename: str) -> str`
  - `def collect_images(html: str, source_dir: Path) -> dict[str, bytes]`
  - `def md_file_to_chapter(md_path: Path) -> Chapter`
  - `def build_epub(chapters: list[Chapter], args: argparse.Namespace) -> epub.EpubBook`
  - `def main() -> None`
- `html.parser` is stdlib; no extra install needed for image-tag scanning in later stories
- Keep all code in a single flat file — no sub-modules

## Test Requirements
- Manual smoke test: `python md_to_epub.py` exits with code 0 (or any non-crash exit; `main()` may currently be a no-op)
- `python -c "from md_to_epub import Chapter; c = Chapter(title='t', html_body='<p/>', images={}); assert c.title == 't'"` passes
- `python -c "import md_to_epub"` produces no import errors

---
<!-- Coding Agent appends timestamped failure notes below this line -->
