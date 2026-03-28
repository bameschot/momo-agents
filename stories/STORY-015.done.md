# STORY-015: PdfExporter, main() Wiring & End-to-End Tests

**Index**: 15
**Attempts**: 1
**Design ref**: design/md-to-pdf-cli.new.md
**Depends on**: STORY-014

## Context
This final story completes `md2pdf.py` by implementing `export_pdf()` (the wkhtmltopdf invocation layer) and wiring all components together in `main()`. It also adds end-to-end integration tests that exercise the full CLI pipeline against real Markdown fixture files and verify that a PDF is actually produced.

## Acceptance Criteria
- [ ] `export_pdf(html: str, output_path: Path) -> None` is implemented:
  1. Writes `html` to a temporary file using `tempfile.NamedTemporaryFile(suffix=".html", delete=False)` (UTF-8).
  2. Builds and runs the following `wkhtmltopdf` command via `subprocess.run(...)` with `stdout` and `stderr` captured:
     ```
     wkhtmltopdf
       --page-size A4
       --margin-top 20mm
       --margin-right 20mm
       --margin-bottom 20mm
       --margin-left 20mm
       --enable-internal-links
       --enable-local-file-access
       <temp_html_path>
       <output_pdf_path>
     ```
  3. If `wkhtmltopdf` exits with a non-zero code: prints its captured `stderr` to the user's `stderr` and calls `sys.exit(1)`.
  4. Deletes the temp HTML file in a `finally` block regardless of success or failure.
- [ ] `main()` orchestrates the full pipeline in this order:
  1. `check_wkhtmltopdf()`
  2. `args = parse_args()`
  3. Read the input `.md` file as UTF-8 text (exit with code 1 + `stderr` message if unreadable).
  4. `result = convert(markdown_text, base_dir=args.input.parent)`
  5. Resolve title: `args.title or result.title or args.input.stem` (in that priority order).
  6. `toc_html = build_toc(result.headings)`
  7. `html = render_page(result, title, toc_html)`
  8. `export_pdf(html, args.output)`
  9. Print `"Written: <output_path>"` to `stdout`.
- [ ] An existing output PDF is overwritten silently (no prompt).
- [ ] The temp HTML file does not persist after a successful run.
- [ ] The temp HTML file does not persist after a failed `wkhtmltopdf` run.

## Implementation Hints
- `subprocess.run(cmd, capture_output=True)` captures both `stdout` and `stderr`; check `.returncode`.
- Wrap the `wkhtmltopdf` subprocess call and temp-file deletion in a `try/finally` block.
- Write the temp file with `f.write(html.encode('utf-8'))` since `NamedTemporaryFile` opens in binary mode by default, or open with `mode='w', encoding='utf-8'`.
- For integration tests: use `subprocess.run(['python', 'md2pdf.py', ...])` so the real CLI entry point is exercised. Skip tests gracefully (via `pytest.mark.skipif`) if `wkhtmltopdf` is not found on the test runner's PATH, so the test suite is still runnable in environments without it.
- Place fixture files in `tests/fixtures/` alongside the existing `md2html.py` test fixtures.

## Test Requirements
- **Unit test — `export_pdf` temp cleanup**: mock `subprocess.run` to return a success result; assert the temp `.html` file is deleted after the call.
- **Unit test — `export_pdf` failure path**: mock `subprocess.run` to return returncode 1 with fake stderr; assert `sys.exit(1)` is raised and the temp file is deleted.
- **Integration test 1 — basic conversion** *(requires wkhtmltopdf)*: fixture with headings, paragraphs, a code block, a table, and a list. Run `python md2pdf.py fixture.md`. Assert returncode 0, output `.pdf` file exists, and file size > 0 bytes.
- **Integration test 2 — explicit output path** (`-o`): assert the PDF is written to the specified path, not the default.
- **Integration test 3 — title override** (`-t`): assert returncode 0 and output file exists (title is embedded in the PDF binary; no assertion on content required beyond successful generation).
- **Integration test 4 — missing input file**: assert returncode != 0 and `stderr` contains an error message.
- **Integration test 5 — default output path**: run with no `-o` flag; assert `<stem>.pdf` exists next to the input file.
- **Integration test 6 — no headings → no ToC**: fixture with only paragraphs; assert returncode 0 and PDF produced (no crash when ToC is empty).
- All tests runnable with `python -m pytest` from the project root without additional setup (wkhtmltopdf-dependent tests auto-skipped when binary is absent).

---
<!-- Coding Agent appends timestamped failure notes below this line -->
