# STORY-015: medium Tests for unbundle() function

**Index**: 15
**Complexity**: medium
**Design ref**: design/bundle-workspace.new.md
**Depends on**: STORY-013

## Context
The `unbundle` function has several distinct code paths — the happy path (no conflicts),
the conflict-and-confirm path, the conflict-and-abort path, missing-zip validation, and
invalid-zip validation. Each path must be covered by an independent, hermetic test.
Tests must never block on real stdin; use `monkeypatch` to inject simulated user responses.

## Acceptance Criteria

### Missing / invalid zip
- [ ] Calling `main(["--unbundle", "--zip", "/nonexistent.zip", str(root)])` exits non-zero and writes to stderr.
- [ ] Calling `main(["--unbundle", "--zip", str(not_a_zip), str(root)])` (where `not_a_zip` is a plain text file) exits non-zero.
- [ ] Calling `main(["--unbundle", str(root)])` (no `--zip`) exits non-zero.

### No-conflict extraction
- [ ] When the zip contains only folders that do NOT exist under `project_root`, `unbundle` extracts all files without prompting the user.
- [ ] After extraction, the expected files are present under `project_root`.
- [ ] The summary line printed to stdout matches `"Extracted N files to <project_root>"` (check `N` equals the actual entry count).

### Conflict detection — prompt displayed
- [ ] When a zip contains a top-level folder that already exists and is non-empty under `project_root`, the prompt text includes `"Overwrite? [y/N]:"`.
- [ ] The prompt lists every conflicting folder, each prefixed with `"  - "` and suffixed with `"/"`.
- [ ] A non-conflicting top-level folder (exists but is empty, or does not exist) does NOT appear in the conflict list.

### Conflict — user aborts (default / explicit n)
- [ ] Simulating Enter (empty string `""`) → prints `"Aborted."` and exits with code 0; no files extracted.
- [ ] Simulating `"n"` → same as above.
- [ ] Simulating `"N"` → same as above.
- [ ] Simulating any other non-`y` string (e.g. `"no"`, `"q"`) → `"Aborted."`, exit 0, no files extracted.

### Conflict — user confirms overwrite
- [ ] Simulating `"y"` → files are extracted (existing files overwritten) and summary is printed.
- [ ] Simulating `"Y"` → same behaviour as `"y"`.

### Extraction correctness
- [ ] File contents extracted from a zip match the original file contents byte-for-byte.
- [ ] Nested directory structure (e.g. `design/subdir/file.md`) is recreated correctly under `project_root`.

## Implementation Hints

Create a helper `make_zip(tmp_path, entries)` that builds a zip with given `{arcname: content}`
entries and returns the zip `Path`:
```python
def make_zip(tmp_path: Path, entries: dict[str, str], name: str = "test.zip") -> Path:
    zip_path = tmp_path / name
    with zipfile.ZipFile(zip_path, "w") as zf:
        for arcname, content in entries.items():
            zf.writestr(arcname, content)
    return zip_path
```

Patch `builtins.input` to simulate stdin:
```python
def test_conflict_abort_enter(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    (root / "design").mkdir()
    (root / "design" / "old.md").write_text("old")  # non-empty → conflict
    zip_path = make_zip(tmp_path, {"design/new.md": "new content"})
    monkeypatch.setattr("builtins.input", lambda _: "")
    with pytest.raises(SystemExit) as exc:
        main(["--unbundle", "--zip", str(zip_path), str(root)])
    assert exc.value.code == 0
    # original file must still be intact
    assert (root / "design" / "old.md").read_text() == "old"
```

For the no-conflict test, set up a fresh `project_root` that has none of the folders present
in the zip — no patching of `input` needed (it should never be called).

For overwrite confirmation:
```python
monkeypatch.setattr("builtins.input", lambda _: "y")
```

Use `capsys.readouterr()` to assert on printed output (summary line, "Aborted.", conflict list).

**Naming note:** if the implementation module is `bundle-workspace.py` (not `bundle.py`), ensure
the import in `test_bundle.py` is consistent with the actual filename.

## Test Requirements
- `pytest` exits 0, zero failures, zero errors.
- `ruff check .` exits 0.
- Every test is hermetic: uses `tmp_path`, patches `builtins.input` where stdin would be read.
- No test relies on the real project root or any real zip file.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
