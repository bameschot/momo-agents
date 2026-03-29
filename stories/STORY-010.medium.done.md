# STORY-010: medium Extend test suite for language-aware exclusions

**Index**: 10
**Complexity**: medium
**Design ref**: design/bundle-workspace.new.md
**Depends on**: STORY-009

## Context
With the language-aware exclusion engine in place, the test suite needs comprehensive coverage of all new behaviour: alias resolution, `build_exclusion_rules`, per-language `should_exclude` correctness, and end-to-end CLI tests for `--language`. Existing tests whose fixtures used the old module-level constants must be updated to pass an `ExclusionRules` instance directly.

## Acceptance Criteria

### `resolve_languages`
- [ ] Canonical names pass through unchanged (`"python"` → `["python"]`).
- [ ] Aliases are resolved correctly: `"py"` → `["python"]`, `"ts"` → `["typescript"]`, `"golang"` → `["go"]`, `"c#"` → `["csharp"]`, `"c++"` → `["cpp"]`.
- [ ] Lookup is case-insensitive: `"Python"`, `"PYTHON"`, `"pYtHoN"` all resolve to `["python"]`.
- [ ] Multiple aliases deduplicate: `["py", "python"]` → `["python"]` (length 1, not 2).
- [ ] Multiple distinct languages: `["py", "ts"]` → `["python", "typescript"]`.
- [ ] Unknown alias exits with non-zero code and writes to stderr (`pytest.raises(SystemExit)`).

### `build_exclusion_rules`
- [ ] `build_exclusion_rules(None)` returns a `ExclusionRules` whose `dir_names` contains `".git"` and also contains at least `".venv"` (python), `"node_modules"` (js), `"target"` (rust/java/kotlin).
- [ ] `build_exclusion_rules(["python"])` contains `".git"` and `".venv"` in `dir_names` but does NOT contain `"node_modules"`.
- [ ] `build_exclusion_rules(["javascript"])` contains `"node_modules"` but does NOT contain `".venv"`.
- [ ] `build_exclusion_rules(["javascript", "typescript"])` produces the same `dir_names` as `build_exclusion_rules(["javascript"])` (they share the same pattern set).
- [ ] `build_exclusion_rules(["rust"])` contains only `"target"` (plus `".git"`) in `dir_names`, with empty `dir_globs`, `file_suffixes`, and `rel_paths`.

### `should_exclude` with explicit rules
- [ ] Python rules: `.venv/`, `__pycache__/` (at any depth), `*.pyc` files, `.pytest_cache/`, and `dist.egg-info/` (matches `*.egg-info` glob) are excluded.
- [ ] JS/TS rules: `node_modules/` at any depth and `.next/` are excluded; `__pycache__/` is NOT excluded.
- [ ] Rust rules: `target/` is excluded; `node_modules/` and `__pycache__/` are not.
- [ ] Ruby rules: `vendor/bundle/` subtree is excluded; `vendor/somethingelse/` is NOT excluded.
- [ ] PHP rules: `var/cache/` and `var/log/` subtrees are excluded; bare `var/` is not.
- [ ] C/C++ rules: directory named `cmake-build-debug` is excluded (matches `cmake-build-*` glob); `.o` and `.dll` files are excluded.
- [ ] All rules: `.git/` is always excluded regardless of the language set.
- [ ] A normal source file (e.g. `src/main.py`) is not excluded under any single-language rule set.

### `create_zip` with language rules
- [ ] When called with Python rules, the resulting zip does not contain `__pycache__/` entries or `*.pyc` files but does contain `node_modules/` contents (if present in the fixture).
- [ ] When called with JS rules, the resulting zip does not contain `node_modules/` entries but does contain `__pycache__/` contents (if present in the fixture).

### CLI integration (`main`)
- [ ] `--language python` runs successfully and the confirmation line includes `"python"`.
- [ ] `--language py ts` runs successfully and the confirmation line includes `"python"` and `"typescript"`.
- [ ] No `--language` runs successfully and the confirmation line includes `"all"`.
- [ ] `--language unknownlang` exits with non-zero code.
- [ ] `--language PYTHON` (upper-case) resolves correctly and runs successfully.

## Implementation Hints

Use the `capsys` pytest fixture to capture stdout and assert on confirmation message content:
```python
def test_confirmation_includes_language(tmp_path, capsys):
    root = _setup_project(tmp_path)
    main([str(root), "--language", "python", "--output", str(tmp_path / "out")])
    captured = capsys.readouterr()
    assert "python" in captured.out
    assert "all" not in captured.out
```

For `should_exclude` tests, build rules explicitly rather than going through `main`:
```python
from bundle import build_exclusion_rules, should_exclude

def test_python_excludes_pycache(tmp_path):
    rules = build_exclusion_rules(["python"])
    root = tmp_path / "proj"
    root.mkdir()
    pycache_file = root / "pkg" / "__pycache__" / "mod.cpython-311.pyc"
    pycache_file.parent.mkdir(parents=True)
    pycache_file.write_text("")
    assert should_exclude(pycache_file, root, rules) is True

def test_js_does_not_exclude_pycache(tmp_path):
    rules = build_exclusion_rules(["javascript"])
    root = tmp_path / "proj"
    root.mkdir()
    pycache_file = root / "__pycache__" / "mod.pyc"
    pycache_file.parent.mkdir()
    pycache_file.write_text("")
    assert should_exclude(pycache_file, root, rules) is False
```

For `vendor/bundle` vs `vendor/other` (Ruby):
```python
def test_ruby_excludes_vendor_bundle_only(tmp_path):
    rules = build_exclusion_rules(["ruby"])
    root = tmp_path / "proj"
    root.mkdir()
    vb = root / "vendor" / "bundle" / "gem.rb"
    vb.parent.mkdir(parents=True); vb.write_text("")
    vo = root / "vendor" / "other" / "lib.rb"
    vo.parent.mkdir(parents=True); vo.write_text("")
    assert should_exclude(vb, root, rules) is True
    assert should_exclude(vo, root, rules) is False
```

All tests must use `tmp_path` and must not rely on the real project root.

## Test Requirements
- `pytest` exits 0 with zero failures and zero errors.
- `ruff check .` (from `workspace/`) exits 0.
- Every new test is independent and repeatable (no shared mutable state, no real filesystem dependencies).

---
<!-- Coding Agent appends timestamped failure notes below this line -->
