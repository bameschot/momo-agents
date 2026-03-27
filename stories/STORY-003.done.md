# STORY-003: Image Embedder

**Index**: 3
**Attempts**: 1
**Design ref**: design/md-to-html-cli.md
**Depends on**: STORY-001

## Context
Implements `embed_image()`, which converts a local image `src` path into a Base64 data URI so the generated HTML is fully self-contained. This component is independent of both the block and inline parsers and can be developed and tested in isolation. The inline parser (STORY-004) will call it when processing image tags.

## Acceptance Criteria
- [ ] `embed_image(src: str, base_dir: Path) -> str` is implemented.
- [ ] **Local files**: path is resolved relative to `base_dir`. File bytes are read, MIME type is determined from extension, and a `data:<mime>;base64,<data>` string is returned.
- [ ] Supported MIME types: `.png` → `image/png`, `.jpg` / `.jpeg` → `image/jpeg`, `.gif` → `image/gif`, `.webp` → `image/webp`, `.svg` → `image/svg+xml`.
- [ ] **HTTP/HTTPS URLs**: returned unchanged (no network request made).
- [ ] **Missing local file**: a warning is printed to `stderr` (format: `Warning: image not found: <path>`), and the original `src` string is returned unchanged.
- [ ] **Unknown extension**: treated as a missing/unembeddable file — print a warning to `stderr` and return the original `src`.
- [ ] The function must not raise exceptions under any supported input condition.

## Implementation Hints
- Use `base64.b64encode(bytes).decode('ascii')` from the stdlib `base64` module.
- Detect HTTP/HTTPS by checking if `src.startswith(('http://', 'https://'))`.
- Resolve the path with `(base_dir / src).resolve()` and check `.exists()` before reading.
- Use a dict for the extension→MIME mapping so adding new types later is trivial.
- Keep the function pure/side-effect-free aside from the `stderr` warning print.

## Test Requirements
- Test with a real `.png` or `.jpg` fixture file: verify return value starts with `data:image/png;base64,` (or appropriate MIME).
- Test with an HTTP URL: verify the URL is returned unchanged.
- Test with a nonexistent local path: verify warning is printed to `stderr` and original `src` is returned.
- Test with an unsupported extension (e.g. `.bmp`): verify warning is printed and original `src` is returned.
- All tests must pass without network access.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
