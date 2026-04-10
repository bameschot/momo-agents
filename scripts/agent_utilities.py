"""Shared agent utilities for all momo-agents."""
import json
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
    """Rename the story file based on the outcome sentinel written by the LLM session.

    Reads the outcome sentinel (expected content: 'done' or 'failed').
    Renames .working.md accordingly and deletes the sentinel.
    If the sentinel is absent or unrecognised, resets to .ready.md so another agent can retry.

    This must be called in Python after the LLM session returns, not inside it,
    so the rename always happens on the main branch and never on a story branch.
    """
    if not story_path.exists():
        print(f"[{agent_name}] WARNING: story file {story_path.name} missing after session — skipping finalise.")
        return

    outcome = outcome_file.read_text().strip() if outcome_file.exists() else ""
    stem = story_path.name.replace(".working.md", "")

    if outcome == "done":
        dest = story_path.with_name(stem + ".done.md")
        story_path.rename(dest)
        append_run_log(run_log, agent_name, f"story done: {dest.name}")
    elif outcome == "failed":
        dest = story_path.with_name(stem + ".failed.md")
        story_path.rename(dest)
        append_run_log(run_log, agent_name, f"story failed: {dest.name}")
    else:
        dest = story_path.with_name(stem + ".ready.md")
        story_path.rename(dest)
        print(f"[{agent_name}] No outcome written — reset {story_path.name} → {dest.name}.")
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
