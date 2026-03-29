"""Tests for bundle.py.

Use the `tmp_path` pytest fixture for all filesystem work — tests must not
depend on the real project root or any real design/ directory.
"""

from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

import pytest

# Make sure bundle.py is importable when tests run from workspace/
sys.path.insert(0, str(Path(__file__).parent.parent))

from bundle import (  # noqa: E402
    build_exclusion_rules,
    create_zip,
    main,
    parse_args,
    resolve_languages,
    resolve_zip_name,
    should_exclude,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_project(tmp_path: Path, design_files: dict[str, float] | None = None) -> Path:
    """Create a minimal fake project tree under *tmp_path*.

    *design_files* maps filename → mtime offset in seconds (relative to a base time).
    Returns the project root path.
    """
    root = tmp_path / "project"
    root.mkdir()
    (root / "design").mkdir()
    (root / "stories").mkdir()
    return root


def create_design_file(design_dir: Path, name: str, mtime: float | None = None) -> Path:
    """Create a design file with optional explicit mtime."""
    path = design_dir / name
    path.write_text(f"# {name}\n")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


# ---------------------------------------------------------------------------
# resolve_zip_name
# ---------------------------------------------------------------------------


class TestResolveZipName:
    """Tests for resolve_zip_name()."""

    def test_picks_most_recently_modified_md(self, tmp_path: Path) -> None:
        root = make_project(tmp_path)
        design_dir = root / "design"
        base_time = 1_000_000.0
        create_design_file(design_dir, "older.md", mtime=base_time)
        create_design_file(design_dir, "newer.md", mtime=base_time + 100)
        result = resolve_zip_name(root)
        assert result == "newer"

    def test_strips_all_extensions(self, tmp_path: Path) -> None:
        root = make_project(tmp_path)
        design_dir = root / "design"
        create_design_file(design_dir, "my-feature.new.md")
        result = resolve_zip_name(root)
        assert result == "my-feature"

    def test_exits_when_no_md_files(self, tmp_path: Path) -> None:
        root = make_project(tmp_path)
        # design/ exists but has no .md files
        (root / "design" / "readme.txt").write_text("not markdown")
        with pytest.raises(SystemExit):
            resolve_zip_name(root)


# ---------------------------------------------------------------------------
# should_exclude
# ---------------------------------------------------------------------------


class TestIsExcluded:
    """Tests for should_exclude()."""

    def test_excludes_git_directory(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = build_exclusion_rules(None)
        # .git at root
        git_file = root / ".git" / "HEAD"
        git_file.parent.mkdir()
        git_file.write_text("ref: refs/heads/main\n")
        assert should_exclude(git_file, root, rules) is True

        # .git nested at depth
        deep_git = root / "subdir" / ".git" / "config"
        deep_git.parent.mkdir(parents=True)
        deep_git.write_text("")
        assert should_exclude(deep_git, root, rules) is True

    def test_excludes_pycache(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = build_exclusion_rules(None)
        pycache_file = root / "__pycache__" / "module.cpython-311.pyc"
        pycache_file.parent.mkdir()
        pycache_file.write_text("")
        assert should_exclude(pycache_file, root, rules) is True

        # nested __pycache__
        nested = root / "pkg" / "__pycache__" / "foo.pyc"
        nested.parent.mkdir(parents=True)
        nested.write_text("")
        assert should_exclude(nested, root, rules) is True

    def test_excludes_node_modules(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = build_exclusion_rules(None)
        nm_file = root / "node_modules" / "lodash" / "index.js"
        nm_file.parent.mkdir(parents=True)
        nm_file.write_text("")
        assert should_exclude(nm_file, root, rules) is True

    def test_excludes_pyc_files(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = build_exclusion_rules(None)
        pyc = root / "module.pyc"
        pyc.write_text("")
        assert should_exclude(pyc, root, rules) is True

    def test_includes_normal_files(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = build_exclusion_rules(None)
        (root / "design").mkdir()
        normal = root / "design" / "foo.md"
        normal.write_text("# design doc\n")
        assert should_exclude(normal, root, rules) is False

        src_file = root / "bundle.py"
        src_file.write_text("# source\n")
        assert should_exclude(src_file, root, rules) is False

    def test_language_specific_rules_exclude_correctly(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        # Python-only rules should exclude __pycache__ but not node_modules
        python_rules = build_exclusion_rules(["python"])
        pycache_file = root / "__pycache__" / "foo.pyc"
        pycache_file.parent.mkdir()
        pycache_file.write_text("")
        assert should_exclude(pycache_file, root, python_rules) is True

        nm_file = root / "node_modules" / "index.js"
        nm_file.parent.mkdir(parents=True)
        nm_file.write_text("")
        assert should_exclude(nm_file, root, python_rules) is False


# ---------------------------------------------------------------------------
# create_zip
# ---------------------------------------------------------------------------


class TestCreateBundle:
    """Tests for create_zip()."""

    def _make_project_with_files(self, tmp_path: Path) -> tuple[Path, Path]:
        """Return (project_root, zip_path) with some content files."""
        root = tmp_path / "project"
        root.mkdir()
        (root / "design").mkdir()
        (root / "design" / "spec.md").write_text("# spec\n")
        (root / "hello.txt").write_text("hello\n")
        zip_path = tmp_path / "output.zip"
        return root, zip_path

    def test_creates_zip_at_expected_path(self, tmp_path: Path) -> None:
        root, zip_path = self._make_project_with_files(tmp_path)
        rules = build_exclusion_rules(None)
        create_zip(root, zip_path, rules)
        assert zip_path.exists()
        assert zipfile.is_zipfile(zip_path)

    def test_zip_contains_relative_paths(self, tmp_path: Path) -> None:
        root, zip_path = self._make_project_with_files(tmp_path)
        rules = build_exclusion_rules(None)
        create_zip(root, zip_path, rules)
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        # All paths must be relative (no leading slash, no absolute references)
        for name in names:
            assert not name.startswith("/"), f"Absolute path in zip: {name}"
            assert not Path(name).is_absolute(), f"Absolute path in zip: {name}"
        # The design/spec.md should be in the zip
        assert "design/spec.md" in names or "design\\spec.md" in names or any(
            "spec.md" in n for n in names
        )

    def test_excluded_paths_not_in_zip(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        (root / "design").mkdir()
        (root / "design" / "spec.md").write_text("# spec\n")
        (root / "hello.txt").write_text("hello\n")
        # Add excluded items
        (root / ".git").mkdir()
        (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "foo.pyc").write_text("")
        (root / "module.pyc").write_text("")
        zip_path = tmp_path / "output.zip"
        rules = build_exclusion_rules(None)
        create_zip(root, zip_path, rules)
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        # None of the excluded names should appear
        for name in names:
            assert ".git" not in name.split("/"), f"Excluded .git found: {name}"
            assert "__pycache__" not in name.split("/"), f"Excluded __pycache__ found: {name}"
            assert not name.endswith(".pyc"), f"Excluded .pyc found: {name}"

    def test_overwrites_existing_zip(self, tmp_path: Path) -> None:
        root, zip_path = self._make_project_with_files(tmp_path)
        rules = build_exclusion_rules(None)
        # Create initial zip with one set of content
        create_zip(root, zip_path, rules)

        # Add another file and overwrite
        (root / "extra.txt").write_text("extra content\n")
        create_zip(root, zip_path, rules)

        # The zip should be valid and have more content
        assert zipfile.is_zipfile(zip_path)
        # Should not have doubled entries — it's a fresh write
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        # No duplicate entries
        assert len(names) == len(set(names))
        # Should include extra.txt
        assert any("extra.txt" in n for n in names)

    def test_creates_output_dir_if_missing(self, tmp_path: Path) -> None:
        """main() should create output_dir automatically."""
        root = tmp_path / "project"
        root.mkdir()
        (root / "design").mkdir()
        (root / "design" / "feature.md").write_text("# feature\n")
        (root / "hello.txt").write_text("hello\n")
        output_dir = tmp_path / "nonexistent" / "nested"
        assert not output_dir.exists()

        main(["--bundle", "--output", str(output_dir), str(root)])

        assert output_dir.exists()
        assert any(f.suffix == ".zip" for f in output_dir.iterdir())

    def test_returns_file_count(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        (root / "design").mkdir()
        (root / "design" / "spec.md").write_text("# spec\n")
        (root / "hello.txt").write_text("hello\n")
        (root / "world.txt").write_text("world\n")
        zip_path = tmp_path / "output.zip"
        rules = build_exclusion_rules(None)
        count = create_zip(root, zip_path, rules)
        # 3 non-excluded files: design/spec.md, hello.txt, world.txt
        assert count == 3

        # Verify zip has the same number of entries
        with zipfile.ZipFile(zip_path, "r") as zf:
            assert len(zf.namelist()) == count


# ---------------------------------------------------------------------------
# main / CLI integration
# ---------------------------------------------------------------------------


class TestMainCLI:
    """End-to-end CLI tests via main()."""

    def _setup_project(self, tmp_path: Path, design_name: str = "feature.md") -> Path:
        root = tmp_path / "project"
        root.mkdir()
        (root / "design").mkdir()
        (root / "design" / design_name).write_text("# design\n")
        (root / "hello.txt").write_text("hello\n")
        return root

    def test_defaults_project_root_to_script_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no project_root given, bundle.py directory is used as root."""
        # We need a design/ dir next to bundle.py (the workspace dir)
        import bundle as bundle_module
        script_dir = Path(bundle_module.__file__).parent
        design_dir = script_dir / "design"
        design_dir.mkdir(exist_ok=True)
        design_file = design_dir / "test-default.md"
        design_file.write_text("# test\n")
        try:
            output_dir = tmp_path / "out"
            monkeypatch.setattr(sys, "argv", ["bundle.py", "--bundle", "--output", str(output_dir)])
            main()
            assert output_dir.exists()
            zips = list(output_dir.glob("*.zip"))
            assert len(zips) == 1
            assert zips[0].stem == "test-default"
        finally:
            design_file.unlink(missing_ok=True)

    def test_custom_project_root(self, tmp_path: Path) -> None:
        root = self._setup_project(tmp_path, "my-spec.md")
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        main(["--bundle", str(root), "--output", str(output_dir)])
        zips = list(output_dir.glob("*.zip"))
        assert len(zips) == 1
        assert zips[0].stem == "my-spec"

    def test_custom_output_dir(self, tmp_path: Path) -> None:
        root = self._setup_project(tmp_path, "bundle-spec.new.md")
        output_dir = tmp_path / "custom_out"
        output_dir.mkdir()
        main(["--bundle", str(root), "--output", str(output_dir)])
        assert (output_dir / "bundle-spec.zip").exists()

    def test_exits_on_missing_project_root(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(SystemExit) as exc_info:
            main(["--bundle", str(nonexistent)])
        assert exc_info.value.code != 0

    def test_exits_on_empty_design_dir(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        (root / "design").mkdir()
        # No .md files in design/
        with pytest.raises(SystemExit) as exc_info:
            main(["--bundle", str(root)])
        assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# parse_args and CLI mode flags
# ---------------------------------------------------------------------------


class TestModeFlags:
    """Tests for parse_args() and mode-flag validation."""

    def test_bundle_flag(self) -> None:
        """Test that --bundle flag sets bundle=True and unbundle=False."""
        args = parse_args(["--bundle"])
        assert args.bundle is True
        assert args.unbundle is False

    def test_unbundle_flag_with_zip(self) -> None:
        """Test that --unbundle with --zip sets the correct flags and path."""
        args = parse_args(["--unbundle", "--zip", "/tmp/foo.zip"])
        assert args.unbundle is True
        assert args.bundle is False
        assert args.zip == "/tmp/foo.zip"

    def test_mutual_exclusion_raises(self) -> None:
        """Test that --bundle and --unbundle together raise SystemExit."""
        with pytest.raises(SystemExit):
            parse_args(["--bundle", "--unbundle"])

    def test_no_mode_raises(self) -> None:
        """Test that no mode argument raises SystemExit with non-zero code."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args([])
        assert exc_info.value.code != 0

    def test_unbundle_without_zip_does_not_raise_in_parse(self) -> None:
        """Test that --unbundle without --zip does not raise in parse_args.

        Zip validation happens at runtime, not during argument parsing.
        """
        args = parse_args(["--unbundle"])
        assert args.unbundle is True
        assert args.zip is None

    def test_main_bundle_mode_end_to_end(self, tmp_path: Path) -> None:
        """Test that main() with --bundle mode produces a zip file."""
        root = tmp_path / "project"
        root.mkdir()
        (root / "design").mkdir()
        (root / "design" / "feature.md").write_text("# feature\n")
        (root / "hello.txt").write_text("hello\n")
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        main(["--bundle", str(root), "--output", str(output_dir)])

        # Verify a zip file was created
        zips = list(output_dir.glob("*.zip"))
        assert len(zips) == 1
        assert zips[0].stem == "feature"
        assert zipfile.is_zipfile(zips[0])

    def test_main_unbundle_bad_zip_path(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Test that main() with a bad zip path exits non-zero with error on stderr."""
        root = tmp_path / "project"
        root.mkdir()
        (root / "design").mkdir()
        (root / "design" / "feature.md").write_text("# feature\n")

        with pytest.raises(SystemExit) as exc_info:
            main(["--unbundle", "--zip", "nosuchfile.zip", str(root)])

        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        # Error should mention the missing zip file
        assert "nosuchfile.zip" in captured.err or "not" in captured.err.lower()


# ---------------------------------------------------------------------------
# resolve_languages
# ---------------------------------------------------------------------------


class TestResolveLanguages:
    """Tests for resolve_languages()."""

    def test_canonical_name_passes_through(self) -> None:
        assert resolve_languages(["python"]) == ["python"]

    def test_alias_py(self) -> None:
        assert resolve_languages(["py"]) == ["python"]

    def test_alias_ts(self) -> None:
        assert resolve_languages(["ts"]) == ["typescript"]

    def test_alias_golang(self) -> None:
        assert resolve_languages(["golang"]) == ["go"]

    def test_alias_csharp_symbol(self) -> None:
        assert resolve_languages(["c#"]) == ["csharp"]

    def test_alias_cpp_symbol(self) -> None:
        assert resolve_languages(["c++"]) == ["cpp"]

    def test_case_insensitive_python(self) -> None:
        assert resolve_languages(["Python"]) == ["python"]
        assert resolve_languages(["PYTHON"]) == ["python"]
        assert resolve_languages(["pYtHoN"]) == ["python"]

    def test_deduplication_py_and_python(self) -> None:
        result = resolve_languages(["py", "python"])
        assert result == ["python"]
        assert len(result) == 1

    def test_multiple_distinct_languages(self) -> None:
        result = resolve_languages(["py", "ts"])
        assert result == ["python", "typescript"]

    def test_unknown_alias_exits_nonzero(self, capsys: pytest.CaptureFixture) -> None:
        with pytest.raises(SystemExit) as exc_info:
            resolve_languages(["unknownlang"])
        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "unknownlang" in captured.err


# ---------------------------------------------------------------------------
# build_exclusion_rules
# ---------------------------------------------------------------------------


class TestBuildExclusionRules:
    """Tests for build_exclusion_rules()."""

    def test_none_includes_universal_and_all_languages(self) -> None:
        rules = build_exclusion_rules(None)
        assert ".git" in rules.dir_names
        assert ".venv" in rules.dir_names
        assert "node_modules" in rules.dir_names
        assert "target" in rules.dir_names

    def test_python_contains_git_and_venv_not_node_modules(self) -> None:
        rules = build_exclusion_rules(["python"])
        assert ".git" in rules.dir_names
        assert ".venv" in rules.dir_names
        assert "node_modules" not in rules.dir_names

    def test_javascript_contains_node_modules_not_venv(self) -> None:
        rules = build_exclusion_rules(["javascript"])
        assert "node_modules" in rules.dir_names
        assert ".venv" not in rules.dir_names

    def test_javascript_and_typescript_same_dir_names_as_javascript(self) -> None:
        rules_js = build_exclusion_rules(["javascript"])
        rules_jsts = build_exclusion_rules(["javascript", "typescript"])
        assert rules_jsts.dir_names == rules_js.dir_names

    def test_rust_contains_only_target_and_git(self) -> None:
        rules = build_exclusion_rules(["rust"])
        assert ".git" in rules.dir_names
        assert "target" in rules.dir_names
        # Should only have .git + target, no other dirs
        assert rules.dir_names == frozenset({".git", "target"})
        assert rules.dir_globs == ()
        assert rules.file_suffixes == frozenset()
        assert rules.rel_paths == ()


# ---------------------------------------------------------------------------
# should_exclude with explicit language rules
# ---------------------------------------------------------------------------


def _make_root(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    return root


def _make_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    return path


class TestShouldExcludeLanguageRules:
    """Tests for should_exclude() with per-language ExclusionRules."""

    # --- Python ---

    def test_python_excludes_venv(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["python"])
        root = _make_root(tmp_path)
        f = _make_file(root / ".venv" / "lib" / "python3.11" / "site.py")
        assert should_exclude(f, root, rules) is True

    def test_python_excludes_pycache_at_any_depth(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["python"])
        root = _make_root(tmp_path)
        f = _make_file(root / "pkg" / "__pycache__" / "mod.cpython-311.pyc")
        assert should_exclude(f, root, rules) is True

    def test_python_excludes_pyc_files(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["python"])
        root = _make_root(tmp_path)
        f = _make_file(root / "module.pyc")
        assert should_exclude(f, root, rules) is True

    def test_python_excludes_pytest_cache(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["python"])
        root = _make_root(tmp_path)
        f = _make_file(root / ".pytest_cache" / "v" / "cache" / "lastfailed")
        assert should_exclude(f, root, rules) is True

    def test_python_excludes_egg_info_via_glob(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["python"])
        root = _make_root(tmp_path)
        f = _make_file(root / "dist.egg-info" / "PKG-INFO")
        assert should_exclude(f, root, rules) is True

    # --- JavaScript / TypeScript ---

    def test_js_excludes_node_modules_at_any_depth(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["javascript"])
        root = _make_root(tmp_path)
        f = _make_file(root / "app" / "node_modules" / "lodash" / "index.js")
        assert should_exclude(f, root, rules) is True

    def test_js_excludes_next(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["javascript"])
        root = _make_root(tmp_path)
        f = _make_file(root / ".next" / "cache" / "webpack" / "client.js")
        assert should_exclude(f, root, rules) is True

    def test_js_does_not_exclude_pycache(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["javascript"])
        root = _make_root(tmp_path)
        f = _make_file(root / "__pycache__" / "mod.pyc")
        assert should_exclude(f, root, rules) is False

    def test_ts_excludes_node_modules(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["typescript"])
        root = _make_root(tmp_path)
        f = _make_file(root / "node_modules" / "react" / "index.js")
        assert should_exclude(f, root, rules) is True

    # --- Rust ---

    def test_rust_excludes_target(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["rust"])
        root = _make_root(tmp_path)
        f = _make_file(root / "target" / "debug" / "myapp")
        assert should_exclude(f, root, rules) is True

    def test_rust_does_not_exclude_node_modules(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["rust"])
        root = _make_root(tmp_path)
        f = _make_file(root / "node_modules" / "pkg" / "index.js")
        assert should_exclude(f, root, rules) is False

    def test_rust_does_not_exclude_pycache(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["rust"])
        root = _make_root(tmp_path)
        f = _make_file(root / "__pycache__" / "mod.pyc")
        assert should_exclude(f, root, rules) is False

    # --- Ruby ---

    def test_ruby_excludes_vendor_bundle(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["ruby"])
        root = _make_root(tmp_path)
        vb = _make_file(root / "vendor" / "bundle" / "gem.rb")
        assert should_exclude(vb, root, rules) is True

    def test_ruby_does_not_exclude_vendor_other(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["ruby"])
        root = _make_root(tmp_path)
        vo = _make_file(root / "vendor" / "other" / "lib.rb")
        assert should_exclude(vo, root, rules) is False

    # --- PHP ---

    def test_php_excludes_var_cache(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["php"])
        root = _make_root(tmp_path)
        f = _make_file(root / "var" / "cache" / "prod" / "Container.php")
        assert should_exclude(f, root, rules) is True

    def test_php_excludes_var_log(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["php"])
        root = _make_root(tmp_path)
        f = _make_file(root / "var" / "log" / "dev.log")
        assert should_exclude(f, root, rules) is True

    def test_php_does_not_exclude_bare_var(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["php"])
        root = _make_root(tmp_path)
        f = _make_file(root / "var" / "config.php")
        assert should_exclude(f, root, rules) is False

    # --- C / C++ ---

    def test_cpp_excludes_cmake_build_dir_via_glob(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["cpp"])
        root = _make_root(tmp_path)
        f = _make_file(root / "cmake-build-debug" / "CMakeFiles" / "main.cpp.o")
        assert should_exclude(f, root, rules) is True

    def test_c_excludes_cmake_build_dir_via_glob(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["c"])
        root = _make_root(tmp_path)
        f = _make_file(root / "cmake-build-release" / "libfoo.a")
        assert should_exclude(f, root, rules) is True

    def test_cpp_excludes_object_files(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["cpp"])
        root = _make_root(tmp_path)
        f = _make_file(root / "src" / "main.o")
        assert should_exclude(f, root, rules) is True

    def test_cpp_excludes_dll_files(self, tmp_path: Path) -> None:
        rules = build_exclusion_rules(["cpp"])
        root = _make_root(tmp_path)
        f = _make_file(root / "lib" / "mylib.dll")
        assert should_exclude(f, root, rules) is True

    # --- Universal ---

    def test_git_always_excluded_for_any_language(self, tmp_path: Path) -> None:
        for lang in ["python", "javascript", "rust", "ruby", "php", "cpp"]:
            rules = build_exclusion_rules([lang])
            lang_dir = tmp_path / lang
            lang_dir.mkdir(parents=True, exist_ok=True)
            root = lang_dir / "proj"
            root.mkdir()
            f = _make_file(root / ".git" / "HEAD")
            assert should_exclude(f, root, rules) is True, f".git not excluded for {lang}"

    def test_normal_source_file_not_excluded_any_single_language(
        self, tmp_path: Path
    ) -> None:
        for lang in ["python", "javascript", "rust", "ruby", "php", "cpp"]:
            rules = build_exclusion_rules([lang])
            lang_dir = tmp_path / lang
            lang_dir.mkdir(parents=True, exist_ok=True)
            root = lang_dir / "proj"
            root.mkdir()
            f = _make_file(root / "src" / "main.py")
            assert should_exclude(f, root, rules) is False, f"src/main.py excluded for {lang}"


# ---------------------------------------------------------------------------
# create_zip with language-specific rules
# ---------------------------------------------------------------------------


class TestCreateZipLanguageRules:
    """Tests for create_zip() with language-specific ExclusionRules."""

    def _make_mixed_project(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create a project with both Python and JS artifacts present."""
        root = tmp_path / "project"
        root.mkdir()
        (root / "design").mkdir()
        (root / "design" / "spec.md").write_text("# spec\n")
        (root / "src" / "main.py").parent.mkdir(parents=True)
        (root / "src" / "main.py").write_text("print('hello')\n")
        # Python artifacts
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "main.cpython-311.pyc").write_text("")
        (root / "src" / "__pycache__").mkdir()
        (root / "src" / "__pycache__" / "main.pyc").write_text("")
        # JS artifacts
        (root / "node_modules" / "lodash").mkdir(parents=True)
        (root / "node_modules" / "lodash" / "index.js").write_text("module.exports = {};\n")
        zip_path = tmp_path / "output.zip"
        return root, zip_path

    def test_python_rules_exclude_pycache_and_pyc(self, tmp_path: Path) -> None:
        root, zip_path = self._make_mixed_project(tmp_path)
        rules = build_exclusion_rules(["python"])
        create_zip(root, zip_path, rules)
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        # No __pycache__ entries
        for name in names:
            assert "__pycache__" not in name.split("/"), f"__pycache__ found: {name}"
            assert not name.endswith(".pyc"), f".pyc found: {name}"

    def test_python_rules_keep_node_modules(self, tmp_path: Path) -> None:
        root, zip_path = self._make_mixed_project(tmp_path)
        rules = build_exclusion_rules(["python"])
        create_zip(root, zip_path, rules)
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        # node_modules should be present
        assert any("node_modules" in name for name in names), (
            "node_modules not found with python rules"
        )

    def test_js_rules_exclude_node_modules(self, tmp_path: Path) -> None:
        root, zip_path = self._make_mixed_project(tmp_path)
        rules = build_exclusion_rules(["javascript"])
        create_zip(root, zip_path, rules)
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        for name in names:
            assert "node_modules" not in name.split("/"), f"node_modules found: {name}"

    def test_js_rules_keep_pycache(self, tmp_path: Path) -> None:
        root, zip_path = self._make_mixed_project(tmp_path)
        rules = build_exclusion_rules(["javascript"])
        create_zip(root, zip_path, rules)
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        # __pycache__ should be present (JS rules don't exclude it)
        assert any("__pycache__" in name for name in names), (
            "__pycache__ not found with js rules"
        )


# ---------------------------------------------------------------------------
# CLI integration: --language flag
# ---------------------------------------------------------------------------


class TestMainLanguageCLI:
    """End-to-end CLI tests for --language flag."""

    def _setup_project(self, tmp_path: Path) -> Path:
        root = tmp_path / "project"
        root.mkdir()
        (root / "design").mkdir()
        (root / "design" / "feature.md").write_text("# design\n")
        (root / "hello.txt").write_text("hello\n")
        return root

    def test_language_python_confirmation_includes_python(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        root = self._setup_project(tmp_path)
        output_dir = tmp_path / "out"
        main(["--bundle", str(root), "--language", "python", "--output", str(output_dir)])
        captured = capsys.readouterr()
        assert "python" in captured.out

    def test_language_py_ts_confirmation_includes_python_and_typescript(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        root = self._setup_project(tmp_path)
        output_dir = tmp_path / "out"
        main(["--bundle", str(root), "--language", "py", "ts", "--output", str(output_dir)])
        captured = capsys.readouterr()
        assert "python" in captured.out
        assert "typescript" in captured.out

    def test_no_language_confirmation_includes_all(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        root = self._setup_project(tmp_path)
        output_dir = tmp_path / "out"
        main(["--bundle", str(root), "--output", str(output_dir)])
        captured = capsys.readouterr()
        assert "all" in captured.out

    def test_unknown_language_exits_nonzero(self, tmp_path: Path) -> None:
        root = self._setup_project(tmp_path)
        output_dir = tmp_path / "out"
        with pytest.raises(SystemExit) as exc_info:
            main(["--bundle", str(root), "--language", "unknownlang", "--output", str(output_dir)])
        assert exc_info.value.code != 0

    def test_language_upper_case_resolves_correctly(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        root = self._setup_project(tmp_path)
        output_dir = tmp_path / "out"
        main(["--bundle", str(root), "--language", "PYTHON", "--output", str(output_dir)])
        captured = capsys.readouterr()
        assert "python" in captured.out
