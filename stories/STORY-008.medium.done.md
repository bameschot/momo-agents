# STORY-008: medium Refactor exclusion engine to be language-aware

**Index**: 8
**Complexity**: medium
**Design ref**: design/bundle-workspace.new.md
**Depends on**: STORY-007

## Context
The current `should_exclude` function consults three module-level constants (`EXCLUDED_DIRS`, `EXCLUDED_FILES`, `EXCLUDED_SUFFIXES`) whose values are hard-coded for one implicit "all-language" mode. This story replaces that approach with a dynamic `ExclusionRules` object built at runtime from the selected language(s). The `.git` directory remains a universal exclusion applied regardless of language choice. The old module-level exclusion constants are removed.

## Acceptance Criteria
- [ ] The module-level constants `EXCLUDED_DIRS`, `EXCLUDED_FILES`, and `EXCLUDED_SUFFIXES` are removed from `bundle.py`.
- [ ] A named structure `ExclusionRules` (dataclass or `NamedTuple`) exists with fields: `dir_names: frozenset[str]`, `dir_globs: tuple[str, ...]`, `file_suffixes: frozenset[str]`, `rel_paths: tuple[str, ...]`.
- [ ] `build_exclusion_rules(canonical_languages: list[str] | None) -> ExclusionRules` exists:
  - When `canonical_languages` is `None` (no `--language`), it unions all entries in `LANGUAGE_EXCLUSIONS` across all 12 languages and always adds `".git"` to `dir_names`.
  - When `canonical_languages` is a non-empty list, it unions only the entries for those languages and always adds `".git"` to `dir_names`.
- [ ] `should_exclude(path: Path, project_root: Path, rules: ExclusionRules) -> bool` is updated to accept `rules` as a third argument and uses it instead of the old constants:
  - A path component in `rules.dir_names` at any depth → excluded.
  - A directory-level component matching any pattern in `rules.dir_globs` (via `fnmatch.fnmatch`) at any depth → excluded.
  - A file whose `suffix` is in `rules.file_suffixes` → excluded.
  - A relative path whose string form starts with any entry in `rules.rel_paths` (e.g. `"vendor/bundle"`) → excluded; use forward-slash normalisation for cross-platform safety.
- [ ] `create_zip(project_root: Path, zip_path: Path, rules: ExclusionRules) -> int` accepts `rules` as a third argument and passes it to every `should_exclude` call.
- [ ] `main` calls `build_exclusion_rules(canonical_langs)`, then passes the resulting `rules` to `create_zip`.
- [ ] Running `python bundle.py` with no arguments (default project root, no `--language`) still produces a valid zip that excludes `.git` and the union of all language exclusion patterns.
- [ ] Running `python bundle.py --language python` produces a zip that excludes Python-specific dirs/files but does NOT exclude `node_modules` (unless it happens to match another active rule).
- [ ] `ruff check .` (from `workspace/`) exits 0.

## Implementation Hints

```python
import fnmatch
from typing import NamedTuple

UNIVERSAL_DIRS = frozenset({".git"})

class ExclusionRules(NamedTuple):
    dir_names:    frozenset[str]
    dir_globs:    tuple[str, ...]
    file_suffixes: frozenset[str]
    rel_paths:    tuple[str, ...]


def build_exclusion_rules(canonical_languages: list[str] | None) -> ExclusionRules:
    langs = list(LANGUAGE_EXCLUSIONS.keys()) if canonical_languages is None else canonical_languages
    dir_names:    set[str]  = set(UNIVERSAL_DIRS)
    dir_globs:    list[str] = []
    file_suffixes: set[str] = set()
    rel_paths:    list[str] = []
    for lang in langs:
        spec = LANGUAGE_EXCLUSIONS[lang]
        dir_names.update(spec["dirs"])
        dir_globs.extend(g for g in spec["dir_globs"] if g not in dir_globs)
        file_suffixes.update(spec["suffixes"])
        rel_paths.extend(p for p in spec["rel_paths"] if p not in rel_paths)
    return ExclusionRules(
        dir_names=frozenset(dir_names),
        dir_globs=tuple(dir_globs),
        file_suffixes=frozenset(file_suffixes),
        rel_paths=tuple(rel_paths),
    )


def should_exclude(path: Path, project_root: Path, rules: ExclusionRules) -> bool:
    try:
        rel = path.relative_to(project_root)
    except ValueError:
        return True

    parts = rel.parts

    # Exact directory-name match at any depth
    if rules.dir_names & set(parts):
        return True

    # Glob match on any path component
    for part in parts:
        if any(fnmatch.fnmatch(part, pattern) for pattern in rules.dir_globs):
            return True

    # Multi-segment path prefix (normalise separators)
    rel_str = "/".join(parts)
    for rp in rules.rel_paths:
        if rel_str == rp or rel_str.startswith(rp + "/"):
            return True

    # File suffix
    if path.suffix in rules.file_suffixes:
        return True

    return False
```

Update `create_zip` signature to `create_zip(project_root, zip_path, rules)` and pass `rules` into both `should_exclude` call sites within it.

In `main`, after resolving `canonical_langs`:
```python
rules = build_exclusion_rules(canonical_langs)
count = create_zip(project_root, zip_path, rules)
```

## Test Requirements
- All existing tests must pass; note that `test_bundle.py` calls `should_exclude(path, root)` with two arguments — those calls must be updated to pass the appropriate `ExclusionRules` instance, or the tests will fail. If existing tests break due to the signature change, they must be fixed in this story (keeping their intent intact). Comprehensive new tests are added in STORY-010.
- `pytest` exits 0.
- `ruff check .` exits 0.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
