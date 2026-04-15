"""Story Orchestrator — watches stories/ and marks stories ready when all dependencies are done.

State files managed by this utility:
  workspace/stories/STORY-NNN.md                       newly written by BA, not yet evaluated
  workspace/stories/STORY-NNN.done.md                  merged and committed by the Merger Agent
  .sentinels/story-orchestrator/STORY-NNN.[easy|medium|hard].ready.md
                                                        deps met — copied here for coding agents
  .sentinels/story-orchestrator/STORY-NNN.[easy|medium|hard].working.md
                                                        claimed by a coding agent
  .sentinels/story-orchestrator/STORY-NNN.[easy|medium|hard].failed.md
                                                        coding agent reported failure

Story state is tracked in the orchestrator dir (.sentinels/story-orchestrator/) rather than
in workspace/stories/ so that git merge operations never touch live state files.
"""
import shutil
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory (agent_utilities, token_logger).
sys.path.insert(0, str(Path(__file__).parent))

import argparse
import re
import time

from agent_utilities import PROJECT_ROOT, resolve_path

DEFAULT_POLL_INTERVAL = 5  # seconds


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Story Orchestrator")
    parser.add_argument(
        "--stories-dir",
        default=str(PROJECT_ROOT / "workspace" / "stories"),
        help="Directory containing story files (default: <project-root>/workspace/stories)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Seconds between polls (default: {DEFAULT_POLL_INTERVAL})",
    )
    return parser.parse_args()


def _parse_fields(path: Path) -> dict[str, str]:
    """Extract **Field**: value pairs from a story file."""
    fields: dict[str, str] = {}
    try:
        for match in re.finditer(r"\*\*([^*]+)\*\*:\s*(.+)", path.read_text()):
            key = match.group(1).strip().lower().replace(" ", "_")
            fields[key] = match.group(2).strip()
    except OSError:
        pass
    return fields


def _complexity(fields: dict[str, str]) -> str:
    return fields.get("complexity", "").lower()


def _dependencies(fields: dict[str, str]) -> list[str]:
    """Return STORY-NNN ids from the Depends on field, or an empty list."""
    raw = fields.get("depends_on", "").strip()
    if not raw or raw.lower() in ("none", "-", "n/a", ""):
        return []
    return re.findall(r"STORY-\d+", raw, re.IGNORECASE)


def _unprocessed_stories(stories_dir: Path) -> list[Path]:
    """Bare STORY-NNN.md files not yet assigned a complexity+state by the orchestrator."""
    return sorted(
        p for p in stories_dir.glob("STORY-*.md")
        if re.match(r"^STORY-\d+\.md$", p.name)
    )


def _process_once(stories_dir: Path, orchestrator_dir: Path) -> int:
    """Evaluate all unprocessed stories and copy eligible ones to the orchestrator dir.

    A story is skipped if any file for it already exists in the orchestrator dir
    (meaning it has been dispatched regardless of its current state there).
    Returns the count of newly dispatched stories.
    """
    done_ids = {p.name.split(".")[0].upper() for p in stories_dir.glob("STORY-*.done.md")}
    marked = 0
    for story_path in _unprocessed_stories(stories_dir):
        story_id = re.match(r"^(STORY-\d+)\.md$", story_path.name).group(1)  # type: ignore[union-attr]

        # Skip if already dispatched to the orchestrator dir (any state).
        if any(orchestrator_dir.glob(f"{story_id}.*")):
            continue

        fields = _parse_fields(story_path)
        complexity = _complexity(fields)

        if complexity not in ("easy", "medium", "hard"):
            print(
                f"  [Orchestrator] Waiting — {story_path.name} has "
                f"missing or unrecognised Complexity: {complexity!r}"
            )
            continue

        deps = _dependencies(fields)
        unmet = [dep for dep in deps if dep.upper() not in done_ids]
        if unmet:
            print(
                f"  [Orchestrator] Waiting — {story_path.name} "
                f"blocked on: {', '.join(unmet)}"
            )
            continue

        ready_path = orchestrator_dir / f"{story_id}.{complexity}.ready.md"
        try:
            shutil.copy2(str(story_path), str(ready_path))
            print(f"  [Orchestrator] {story_path.name} → {ready_path.name} (orchestrator dir)")
            marked += 1
        except OSError as exc:
            print(f"  [Orchestrator] Could not copy {story_path.name}: {exc}")

    return marked


def run(stories_dir: Path, poll_interval: int) -> None:
    sentinels_dir = stories_dir.parent / ".sentinels"
    orchestrator_dir = sentinels_dir / "story-orchestrator"
    pipeline_complete = sentinels_dir / "pipeline_complete"

    orchestrator_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Story Orchestrator] Watching {stories_dir}")
    print(f"[Story Orchestrator] Orchestrator dir: {orchestrator_dir}")
    print(f"[Story Orchestrator] Poll interval: {poll_interval}s")
    print()

    while True:
        if pipeline_complete.exists():
            print("[Story Orchestrator] pipeline_complete sentinel detected — exiting.")
            break

        _process_once(stories_dir, orchestrator_dir)
        time.sleep(poll_interval)


if __name__ == "__main__":
    args = _parse_args()
    stories_dir = resolve_path(args.stories_dir)
    run(stories_dir, args.poll_interval)
