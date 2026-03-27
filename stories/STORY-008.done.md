# STORY-008: Test Suite

**Index**: 8
**Attempts**: 1
**Design ref**: design/md-to-epub.md
**Depends on**: STORY-007

## Context
The tool is complete after STORY-007 but has no automated test coverage. This story adds a `pytest`-based test suite that covers every function in `md_to_epub.py` and verifies the end-to-end pipeline. Tests serve as the living specification and regression safety net for future changes.

## Acceptance Criteria
- [ ] A `tests/` directory is created at the project root with an `__init__.py` (may be empty) and a `test_md_to_epub.py` file
- [ ] `pytest` (added to a `requirements-dev.txt`) can be installed and `pytest tests/` passes with zero failures
- [ ] `test_extract_chapter_title` covers: h1 found, h1 not found (stem fallback), bold inline markup stripped, h1 not on first line
- [ ] `test_collect_images` covers: image present, image missing (warning emitted), remote URL skipped, no images, mixed present/missing
- [ ] `test_md_file_to_chapter` covers: basic conversion, table rendering, fenced code rendering, missing image warning propagation
- [ ] `test_build_epub` covers: returns `EpubBook`, title/author/language set correctly, publisher present/absent, CSS item present, chapter items present, image items present
- [ ] `test_parse_args` covers: all defaults, all flags set explicitly, missing positional arg exits non-zero
- [ ] `test_main_integration` covers: end-to-end single file, end-to-end multi-file, missing input file exits 1, `--output` honoured, default output filename derived from title
- [ ] All tests use `tmp_path` (pytest fixture) for temporary files; no test writes to the real filesystem outside of `tmp_path`
- [ ] No test makes network requests

## Implementation Hints
- `requirements-dev.txt` should contain `pytest>=8.0` and can re-include or `-r requirements.txt` for convenience
- Use `pytest.warns(UserWarning)` to assert that `collect_images` emits warnings for missing images
- Use `unittest.mock.patch('sys.argv', [...])` or pass args directly by temporarily setting `sys.argv` inside each test function; restore via `monkeypatch.setattr`
- For the integration test, verify the output is a valid EPUB/ZIP: `import zipfile; assert zipfile.is_zipfile(str(output_path))`
- Use `capsys` fixture to assert that the success message appears on stdout and errors appear on stderr
- To test `sys.exit(1)` behaviour, use `with pytest.raises(SystemExit) as exc; assert exc.value.code == 1`
- Testing `build_epub` cover-image validation: create a small valid PNG with `PIL.Image` in `tmp_path`, and separately write `b"not an image"` to test the invalid-cover path

## Test Requirements
- `pytest tests/` exits with code 0
- All tests are independent and can run in any order
- No test depends on the current working directory's contents
- Test file is importable without side-effects (`import tests.test_md_to_epub` does nothing)

---
<!-- Coding Agent appends timestamped failure notes below this line -->
