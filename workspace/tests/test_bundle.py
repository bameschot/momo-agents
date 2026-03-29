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

from bundle import create_zip, resolve_zip_name, should_exclude, main  # noqa: E402


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
        # .git at root
        git_file = root / ".git" / "HEAD"
        git_file.parent.mkdir()
        git_file.write_text("ref: refs/heads/main\n")
        assert should_exclude(git_file, root) is True

        # .git nested at depth
        deep_git = root / "subdir" / ".git" / "config"
        deep_git.parent.mkdir(parents=True)
        deep_git.write_text("")
        assert should_exclude(deep_git, root) is True

    def test_excludes_pycache(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        pycache_file = root / "__pycache__" / "module.cpython-311.pyc"
        pycache_file.parent.mkdir()
        pycache_file.write_text("")
        assert should_exclude(pycache_file, root) is True

        # nested __pycache__
        nested = root / "pkg" / "__pycache__" / "foo.pyc"
        nested.parent.mkdir(parents=True)
        nested.write_text("")
        assert should_exclude(nested, root) is True

    def test_excludes_node_modules(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        nm_file = root / "node_modules" / "lodash" / "index.js"
        nm_file.parent.mkdir(parents=True)
        nm_file.write_text("")
        assert should_exclude(nm_file, root) is True

    def test_excludes_dotenv_file(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        dotenv = root / ".env"
        dotenv.write_text("SECRET=abc\n")
        assert should_exclude(dotenv, root) is True

    def test_excludes_pyc_files(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        pyc = root / "module.pyc"
        pyc.write_text("")
        assert should_exclude(pyc, root) is True

    def test_includes_normal_files(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        (root / "design").mkdir()
        normal = root / "design" / "foo.md"
        normal.write_text("# design doc\n")
        assert should_exclude(normal, root) is False

        src_file = root / "bundle.py"
        src_file.write_text("# source\n")
        assert should_exclude(src_file, root) is False


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
        create_zip(root, zip_path)
        assert zip_path.exists()
        assert zipfile.is_zipfile(zip_path)

    def test_zip_contains_relative_paths(self, tmp_path: Path) -> None:
        root, zip_path = self._make_project_with_files(tmp_path)
        create_zip(root, zip_path)
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
        (root / ".env").write_text("SECRET=abc\n")
        (root / "module.pyc").write_text("")
        zip_path = tmp_path / "output.zip"
        create_zip(root, zip_path)
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        # None of the excluded names should appear
        for name in names:
            assert ".git" not in name.split("/"), f"Excluded .git found: {name}"
            assert "__pycache__" not in name.split("/"), f"Excluded __pycache__ found: {name}"
            assert ".env" not in name, f"Excluded .env found: {name}"
            assert not name.endswith(".pyc"), f"Excluded .pyc found: {name}"

    def test_overwrites_existing_zip(self, tmp_path: Path) -> None:
        root, zip_path = self._make_project_with_files(tmp_path)
        # Create initial zip with one set of content
        create_zip(root, zip_path)
        size_first = zip_path.stat().st_size

        # Add another file and overwrite
        (root / "extra.txt").write_text("extra content\n")
        count = create_zip(root, zip_path)
        size_second = zip_path.stat().st_size

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

        main(["--output", str(output_dir), str(root)])

        assert output_dir.exists()
        assert any(f.suffix == ".zip" for f in output_dir.iterdir())

    def test_returns_file_count(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        (root / "design").mkdir()
        (root / "design" / "spec.md").write_text("# spec\n")
        (root / "hello.txt").write_text("hello\n")
        (root / "world.txt").write_text("world\n")
        # Add excluded file — should not be counted
        (root / ".env").write_text("SECRET=abc\n")
        zip_path = tmp_path / "output.zip"
        count = create_zip(root, zip_path)
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

    def test_defaults_project_root_to_script_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
            monkeypatch.setattr(sys, "argv", ["bundle.py", "--output", str(output_dir)])
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
        main([str(root), "--output", str(output_dir)])
        zips = list(output_dir.glob("*.zip"))
        assert len(zips) == 1
        assert zips[0].stem == "my-spec"

    def test_custom_output_dir(self, tmp_path: Path) -> None:
        root = self._setup_project(tmp_path, "bundle-spec.new.md")
        output_dir = tmp_path / "custom_out"
        output_dir.mkdir()
        main([str(root), "--output", str(output_dir)])
        assert (output_dir / "bundle-spec.zip").exists()

    def test_exits_on_missing_project_root(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(SystemExit) as exc_info:
            main([str(nonexistent)])
        assert exc_info.value.code != 0

    def test_exits_on_empty_design_dir(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        (root / "design").mkdir()
        # No .md files in design/
        with pytest.raises(SystemExit) as exc_info:
            main([str(root)])
        assert exc_info.value.code != 0
