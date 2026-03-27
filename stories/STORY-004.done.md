# STORY-004: Image Collection (`collect_images`)

**Index**: 4
**Attempts**: 1
**Design ref**: design/md-to-epub.md
**Depends on**: STORY-001

## Context
Markdown files often embed local images with relative paths. Before assembling the EPUB, we must resolve those paths, read the raw bytes, and hand them to the EPUB builder. Images that cannot be found must not abort the process — they are warned about and skipped, so the rest of the book still renders.

## Acceptance Criteria
- [ ] The function signature is exactly `collect_images(html: str, source_dir: Path) -> dict[str, bytes]`
- [ ] All `<img src="...">` tags in the HTML are detected (case-insensitive tag name; both `src="..."` and `src='...'` quote styles)
- [ ] Each `src` value is resolved relative to `source_dir`; absolute paths and `http://`/`https://` URLs are **skipped silently** (not warned, not included)
- [ ] For each resolvable local path that exists and is readable, the raw file bytes are read and stored in the returned dict under the original `src` string as the key
- [ ] If a local image path cannot be found or read, a warning is emitted via `warnings.warn(...)` (category `UserWarning`) and the image is omitted from the result dict
- [ ] The function returns an empty dict `{}` when the HTML contains no `<img>` tags
- [ ] The function does **not** use `Pillow` — image validation is out of scope here; raw bytes are sufficient

## Implementation Hints
- Use Python's stdlib `html.parser.HTMLParser` (subclass it) to parse `<img>` tags rather than regex — it handles attribute quoting robustly
- Alternatively, `re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)` is simpler and acceptable for the well-formed HTML that `markdown` library produces
- Check for URL schemes: `if src.startswith(('http://', 'https://', 'data:')): continue`
- Use `(source_dir / src).resolve()` then `path.read_bytes()` wrapped in a `try/except (FileNotFoundError, OSError)`
- The returned dict maps the **original** `src` attribute string (unchanged) → bytes, so callers can correlate back to the HTML

## Test Requirements
- HTML with `<img src="logo.png">` and `logo.png` present in `source_dir` → dict contains `{"logo.png": <bytes>}`
- HTML with `<img src="missing.png">` and file absent → empty dict returned, `warnings.warn` called once
- HTML with `<img src="https://example.com/img.png">` → empty dict, no warning
- HTML with no `<img>` tags → returns `{}`
- HTML with two images, one present and one missing → dict has one entry, one warning emitted
- HTML with `src` in single quotes → image is still detected

---
<!-- Coding Agent appends timestamped failure notes below this line -->
