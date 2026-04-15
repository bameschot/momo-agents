"""Shared agent utilities for all momo-agents."""
import fnmatch
import json
import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import anyio

PROJECT_ROOT = Path(__file__).parent.parent
ROLES_DIR = PROJECT_ROOT / "roles"
CLAUDE_ROLES_DIR = ROLES_DIR / "claude_roles"
OLLAMA_ROLES_DIR = ROLES_DIR / "ollama_roles"


def load_role(role_name: str) -> str:
    """Read and return the system prompt for the given role file (without .md extension).

    role_name may include a subdirectory, e.g. 'claude_roles/claude_designer'
    or 'ollama_roles/ollama-business-analyst'.
    """
    return (ROLES_DIR / f"{role_name}.md").read_text()


def resolve_path(raw: str | Path) -> Path:
    """Return an absolute Path, resolving relative paths against PROJECT_ROOT."""
    p = Path(raw)
    return p if p.is_absolute() else PROJECT_ROOT / p


def append_run_log(run_log_path: Path | None, agent_name: str, message: str) -> None:
    """Append a timestamped entry to the run-log.jsonl file (one JSON object per line)."""
    if run_log_path is None:
        return
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_name": agent_name,
        "message": message,
    }
    try:
        run_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(run_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def claim_story(stories_dir: Path, patterns: list[str]) -> Path | None:
    """Atomically claim the lowest-numbered matching .ready story.

    Tries each glob pattern in order, merges all candidates, sorts by name, and
    attempts a POSIX atomic rename of the first unclaimed file to .working.md.
    Returns the new .working path on success, None if nothing could be claimed.
    """
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(stories_dir.glob(pattern))
    for candidate in sorted(candidates, key=lambda p: p.name):
        working = candidate.with_name(candidate.name.replace(".ready.md", ".working.md"))
        try:
            candidate.rename(working)
            return working
        except OSError:
            continue
    return None


def finalise_story(story_path: Path, outcome_file: Path, run_log: Path | None, agent_name: str) -> None:
    """Rename the story file after a coding-agent session that did NOT produce a merge-ready zip.

    Only handles 'failed' and absent/unrecognised outcomes — never 'done'.
    Marking a story as .done.md is exclusively the responsibility of the Merger Agent
    via mark_story_done_after_merge, which runs after a successful git merge.

    Reads the outcome sentinel (expected content: 'failed').
    Renames .working.md to .failed.md on failure, or resets to .ready.md otherwise
    so another agent can retry.

    If the .working.md file is missing (e.g. removed during the agent session), the
    destination file is created directly from the outcome so state is never lost.

    This must be called in Python after the LLM session returns, not inside it.
    """
    outcome = outcome_file.read_text().strip() if outcome_file.exists() else ""
    stem = story_path.name.replace(".working.md", "")

    if outcome == "done":
        # Successful stories stay in .working.md — the Merger Agent is the only
        # actor that may advance them to .done.md (via mark_story_done_after_merge).
        print(f"[{agent_name}] WARNING: 'done' outcome passed to finalise_story — leaving {story_path.name} in .working state for the Merger Agent.")
        if outcome_file.exists():
            outcome_file.unlink()
        return

    if outcome == "failed":
        dest = story_path.with_name(stem + ".failed.md")
    else:
        dest = story_path.with_name(stem + ".ready.md")

    if story_path.exists():
        story_path.rename(dest)
    else:
        print(f"[{agent_name}] WARNING: {story_path.name} missing after session — creating {dest.name} directly.")
        dest.touch()

    if outcome == "failed":
        append_run_log(run_log, agent_name, f"story failed: {dest.name}")
    else:
        print(f"[{agent_name}] No valid outcome written — reset to {dest.name}.")
        append_run_log(run_log, agent_name, f"story reset to ready: {dest.name}")

    if outcome_file.exists():
        outcome_file.unlink()


async def wait_for_workspace(workspace_dir: Path, agent_name: str, poll_interval: int) -> None:
    """Block until workspace_dir/CLAUDE.md exists (scaffolding agent has finished)."""
    claude_md = workspace_dir / "CLAUDE.md"
    if claude_md.exists():
        return
    print(f"[{agent_name}] Waiting for scaffolding to complete ({claude_md}) — polling every {poll_interval}s...")
    while not claude_md.exists():
        await anyio.sleep(poll_interval)
    print(f"[{agent_name}] Workspace ready — proceeding.")


# ─────────────────────────────────────────────────────────────────────────────
# Isolated workspace helpers (git-merge-based pipeline)
# ─────────────────────────────────────────────────────────────────────────────

# Directories always excluded when zipping a temp workspace for the merge-queue.
# .git    — git metadata of the temp workspace; not needed by merger
# stories — state-encoded filenames would conflict when merging in order
# design  — large read-only artefacts already present in main workspace
_ZIP_ALWAYS_EXCLUDE: frozenset[str] = frozenset({".git", "stories", "design"})


# ─────────────────────────────────────────────────────────────────────────────
# Design sentinel helpers
# ─────────────────────────────────────────────────────────────────────────────

def design_feature_name(design_file: Path) -> str:
    """Return the bare feature name from a .new.md design file.

    E.g. 'my-feature.new.md' → 'my-feature'
    """
    return design_file.name.removesuffix(".new.md")


def is_design_processed(sentinels_design_dir: Path, design_file: Path) -> bool:
    """Return True if a processed sentinel exists for this design file."""
    return (sentinels_design_dir / f"{design_feature_name(design_file)}.processed.md").exists()


def mark_design_processed(sentinels_design_dir: Path, design_file: Path) -> None:
    """Write a copy of the design to the sentinels dir, marking it as processed.

    Creates sentinels_design_dir if it does not exist.
    """
    sentinels_design_dir.mkdir(parents=True, exist_ok=True)
    sentinel = sentinels_design_dir / f"{design_feature_name(design_file)}.processed.md"
    sentinel.write_text(design_file.read_text())


def unprocessed_designs(design_dir: Path, sentinels_design_dir: Path) -> list[Path]:
    """Return .new.md files in design_dir that have no processed sentinel."""
    return [
        f for f in sorted(design_dir.glob("*.new.md"))
        if not is_design_processed(sentinels_design_dir, f)
    ]


def get_story_id(story_path: Path) -> str:
    """Return the STORY-NNN identifier from a story filename.

    E.g. 'STORY-003.medium.working.md' → 'STORY-003'
    """
    return story_path.name.split(".")[0]


def copy_workspace_for_story(workspace_dir: Path, sentinels_dir: Path, story_id: str) -> Path:
    """Copy workspace_dir (excluding .sentinels) into sentinels_dir/<story_id>/.

    Returns the path to the new temporary workspace directory.
    An existing temp directory for the same story_id is removed first.
    """
    temp_dir = sentinels_dir / story_id
    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    def _ignore_sentinels(src: str, names: list[str]) -> list[str]:
        return [n for n in names if n == ".sentinels"]

    shutil.copytree(str(workspace_dir), str(temp_dir), ignore=_ignore_sentinels)

    return temp_dir


def _load_gitignore_patterns(workspace_dir: Path) -> list[str]:
    """Return non-comment, non-blank lines from workspace_dir/.gitignore."""
    gitignore = workspace_dir / ".gitignore"
    if not gitignore.exists():
        return []
    patterns: list[str] = []
    for line in gitignore.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def _is_gitignored(rel_path: str, name: str, patterns: list[str]) -> bool:
    """Return True if rel_path or its basename matches any gitignore pattern."""
    for pattern in patterns:
        bare = pattern.rstrip("/")
        if fnmatch.fnmatch(name, bare):
            return True
        if fnmatch.fnmatch(rel_path, bare):
            return True
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def zip_workspace_for_merge(temp_workspace: Path, story_id: str, merge_queue_dir: Path) -> Path:
    """Zip temp_workspace (excluding stories/, design/, .git/, and .gitignore patterns)
    and place it as merge_queue_dir/<story_id>.zip.

    Returns the path to the created zip file.
    """
    merge_queue_dir.mkdir(parents=True, exist_ok=True)
    zip_path = merge_queue_dir / f"{story_id}.zip"
    gitignore_patterns = _load_gitignore_patterns(temp_workspace)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(temp_workspace):
            root_path = Path(root)
            rel_root = root_path.relative_to(temp_workspace)
            at_top = rel_root == Path(".")

            # Filter directories in-place to prune the walk.
            filtered: list[str] = []
            for d in dirs:
                if at_top and d in _ZIP_ALWAYS_EXCLUDE:
                    continue
                rel_d = str(rel_root / d)
                if _is_gitignored(rel_d, d, gitignore_patterns):
                    continue
                filtered.append(d)
            dirs[:] = filtered

            for fname in files:
                rel_file = str(rel_root / fname)
                if not _is_gitignored(rel_file, fname, gitignore_patterns):
                    zf.write(str(root_path / fname), rel_file)

    return zip_path


def get_next_merge_story(merge_queue_dir: Path) -> Path | None:
    """Return the lowest-numbered STORY-NNN.zip in merge_queue_dir, or None."""
    if not merge_queue_dir.exists():
        return None
    zips = sorted(merge_queue_dir.glob("STORY-*.zip"), key=lambda p: p.name)
    return zips[0] if zips else None


def unzip_workspace_for_merge(zip_path: Path, sentinels_dir: Path) -> Path:
    """Unzip a merge-queue zip to sentinels_dir/merge-<story_id>/.

    Any pre-existing directory at that path is removed first.
    Returns the path to the extracted directory.
    """
    story_id = zip_path.stem  # STORY-NNN
    extract_dir = sentinels_dir / f"merge-{story_id}"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(str(extract_dir))
    return extract_dir


def mark_story_done_after_merge(
    stories_dir: Path,
    story_id: str,
    run_log: Path | None,
    agent_name: str,
    orchestrator_dir: Path | None = None,
) -> None:
    """Rename STORY-NNN.md to STORY-NNN.done.md after a successful merge, then commit.

    The bare source story file (STORY-NNN.md) in stories_dir is renamed to
    STORY-NNN.done.md and the change is committed to git so the done state
    persists across team restarts.

    If orchestrator_dir is provided, any files for this story are removed from
    the orchestrator dir so it is no longer visible to coding agents.

    If no STORY-NNN.md is found, logs a warning and returns.
    """
    story_md = stories_dir / f"{story_id}.md"
    if not story_md.exists():
        print(f"[{agent_name}] WARNING: {story_id}.md not found in {stories_dir} — cannot mark done.")
        return
    dest = stories_dir / f"{story_id}.done.md"
    story_md.rename(dest)
    append_run_log(run_log, agent_name, f"story merged and done: {dest.name}")
    print(f"[{agent_name}] Marked {dest.name}")

    # Commit the done-state rename to git so it survives restarts.
    workspace_dir = stories_dir.parent
    try:
        subprocess.run(
            ["git", "add", str(stories_dir)],
            cwd=str(workspace_dir),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"chore: mark {story_id} done"],
            cwd=str(workspace_dir),
            check=True,
            capture_output=True,
        )
        print(f"[{agent_name}] Committed done state for {story_id}.")
    except subprocess.CalledProcessError as exc:
        print(f"[{agent_name}] WARNING: could not commit done state for {story_id}: {exc}")

    # Clean up the orchestrator dir entry so the story is no longer visible to agents.
    if orchestrator_dir is not None and orchestrator_dir.exists():
        for f in orchestrator_dir.glob(f"{story_id}.*"):
            try:
                f.unlink()
            except OSError:
                pass
