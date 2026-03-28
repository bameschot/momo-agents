"""Story Orchestrator — watches stories/ and marks stories ready when all dependencies are done.

Filename convention managed by this utility:
  STORY-NNN.md                        newly written by BA, not yet evaluated
  STORY-NNN.[easy|medium|hard].ready.md   deps met — ready to be claimed by a coding agent
"""
import argparse
import re
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

DEFAULT_POLL_INTERVAL = 5  # seconds


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Story Orchestrator")
    parser.add_argument(
        "--stories-dir",
        default=str(PROJECT_ROOT / "stories"),
        help="Directory containing story files (default: <project-root>/stories)",
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


def _is_done(stories_dir: Path, story_id: str) -> bool:
    """True when any STORY-NNN.[complexity].done.md exists for this story id."""
    return any(stories_dir.glob(f"{story_id.upper()}.*.done.md"))


def _unprocessed_stories(stories_dir: Path) -> list[Path]:
    """Bare STORY-NNN.md files not yet assigned a complexity+state by the orchestrator."""
    return sorted(
        p for p in stories_dir.glob("STORY-*.md")
        if re.match(r"^STORY-\d+\.md$", p.name)
    )


def _process_once(stories_dir: Path) -> int:
    """Evaluate all unprocessed stories and mark eligible ones as ready. Returns count marked."""
    marked = 0
    for story_path in _unprocessed_stories(stories_dir):
        fields = _parse_fields(story_path)
        complexity = _complexity(fields)

        if complexity not in ("easy", "medium", "hard"):
            print(
                f"  [Orchestrator] Waiting — {story_path.name} has "
                f"missing or unrecognised Complexity: {complexity!r}"
            )
            continue

        deps = _dependencies(fields)
        unmet = [dep for dep in deps if not _is_done(stories_dir, dep)]
        if unmet:
            print(
                f"  [Orchestrator] Waiting — {story_path.name} "
                f"blocked on: {', '.join(unmet)}"
            )
            continue

        story_id = re.match(r"^(STORY-\d+)\.md$", story_path.name).group(1)  # type: ignore[union-attr]
        ready_path = stories_dir / f"{story_id}.{complexity}.ready.md"
        try:
            story_path.rename(ready_path)
            print(f"  [Orchestrator] {story_path.name} → {ready_path.name}")
            marked += 1
        except OSError as exc:
            print(f"  [Orchestrator] Could not rename {story_path.name}: {exc}")

    return marked


def run(stories_dir: Path, poll_interval: int) -> None:
    pipeline_complete = PROJECT_ROOT / ".sentinels" / "pipeline_complete"

    print(f"[Story Orchestrator] Watching {stories_dir}")
    print(f"[Story Orchestrator] Poll interval: {poll_interval}s")
    print()

    while True:
        if pipeline_complete.exists():
            print("[Story Orchestrator] pipeline_complete sentinel detected — exiting.")
            break

        _process_once(stories_dir)
        time.sleep(poll_interval)


if __name__ == "__main__":
    args = _parse_args()
    stories_dir = Path(args.stories_dir)
    if not stories_dir.is_absolute():
        stories_dir = PROJECT_ROOT / stories_dir
    run(stories_dir, args.poll_interval)
