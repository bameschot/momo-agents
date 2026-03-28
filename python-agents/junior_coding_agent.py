"""Junior Coding Agent — claims and implements easy stories from stories/."""
import argparse
import re
import anyio
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

from token_logger import log_usage

PROJECT_ROOT = Path(__file__).parent.parent
ROLES_DIR = PROJECT_ROOT / "roles"

POLL_INTERVAL = 60  # seconds between polls when no eligible story is available
ELIGIBLE_COMPLEXITIES = ("easy",)

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Junior Coding Agent (easy stories)")
    parser.add_argument(
        "--stories-dir",
        default=str(PROJECT_ROOT / "stories"),
        help="Directory containing story files (default: <project-root>/stories)",
    )
    parser.add_argument(
        "--workspace-dir",
        default=str(PROJECT_ROOT / "workspace"),
        help="Directory containing the workspace to implement stories in (default: <project-root>/workspace)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--token-log",
        default="",
        help="Path to JSONL file for token usage logging (optional)",
    )
    return parser.parse_args()


def _system_prompt() -> str:
    return (ROLES_DIR / "junior-coding-agent.md").read_text()


def _read_complexity(path: Path) -> str:
    """Extract the Complexity field value from a story file. Returns empty string if not found."""
    try:
        content = path.read_text()
        match = re.search(r"\*\*Complexity\*\*:\s*(\w+)", content)
        return match.group(1).lower() if match else ""
    except OSError:
        return ""


def _unclaimed_eligible_stories(stories_dir: Path) -> list[Path]:
    """Return bare STORY-NNN.md files with an eligible complexity, sorted by filename."""
    candidates = [
        p for p in stories_dir.glob("STORY-*.md")
        if re.match(r"^STORY-\d+\.md$", p.name)
    ]
    return sorted(
        (p for p in candidates if _read_complexity(p) in ELIGIBLE_COMPLEXITIES),
        key=lambda p: p.name,
    )


def _in_progress_stories(stories_dir: Path) -> list[Path]:
    return list(stories_dir.glob("STORY-*.working.md"))


async def _wait_for_eligible_story(stories_dir: Path, pipeline_complete: Path) -> bool:
    """
    Poll until at least one unclaimed easy story exists, then return True.
    Returns False on HALT or pipeline_complete.
    """
    halt_file = stories_dir / "HALT"
    last_status = ""
    while True:
        if halt_file.exists():
            print("[Junior Coding Agent] HALT detected while waiting — exiting.")
            return False

        if pipeline_complete.exists():
            print("[Junior Coding Agent] Pipeline complete sentinel detected — exiting.")
            return False

        eligible = _unclaimed_eligible_stories(stories_dir)
        if eligible:
            return True

        in_progress = _in_progress_stories(stories_dir)
        status = f"in-progress={len(in_progress)}" if in_progress else "all done or no easy stories"
        if status != last_status:
            print(
                f"[Junior Coding Agent] No unclaimed easy story available ({status}). "
                f"Polling every {POLL_INTERVAL}s..."
            )
            last_status = status

        await anyio.sleep(POLL_INTERVAL)


async def run(stories_dir: Path, workspace_dir: Path, model: str, token_log: Path | None) -> None:
    pipeline_complete = PROJECT_ROOT / ".sentinels" / "pipeline_complete"
    halt_file = stories_dir / "HALT"

    if halt_file.exists():
        print("[Junior Coding Agent] HALT file detected on startup — exiting immediately.")
        return

    if not await _wait_for_eligible_story(stories_dir, pipeline_complete):
        print("[Junior Coding Agent] No easy stories to process — exiting.")
        return

    task = (
        f"Project root: {PROJECT_ROOT}\n"
        f"Stories directory: {stories_dir}\n"
        f"Workspace directory: {workspace_dir}\n"
        f"Eligible complexity levels: {', '.join(ELIGIBLE_COMPLEXITIES)}\n\n"
        "Begin the coding agent loop now:\n"
        f"1. Check for {halt_file} — exit immediately if it exists.\n"
        f"2. Scan {stories_dir} for pending stories (STORY-*.md, not .working/.done/.failed/.reviewing).\n"
        f"3. Filter to stories where **Complexity** is one of: {', '.join(ELIGIBLE_COMPLEXITIES)}. "
        "Skip any story whose complexity does not match — those belong to Senior Coding Agents.\n"
        "4. Sort eligible candidates by the **Index** field (ascending). For each candidate, check "
        "**Depends on** and skip if the dependency is not yet .done.md.\n"
        "5. Atomically claim the lowest-index eligible story by renaming "
        "STORY-NNN.md → STORY-NNN.working.md. If the rename fails (another agent claimed "
        "it first), try the next candidate. If no story can be claimed, exit.\n"
        f"6. Read {workspace_dir}/CLAUDE.md for build, test, and lint instructions.\n"
        "7. Increment **Attempts** in the story file header.\n"
        "8. Implement the story's acceptance criteria inside the workspace directory.\n"
        "9. Run tests and linter as instructed in CLAUDE.md.\n"
        f"10. Before committing, check for {halt_file} again — if found, perform the "
        "halt procedure (discard uncommitted changes, rename .working.md back to .md, exit).\n"
        "11. On success: rename .working.md → .done.md, commit workspace changes, loop to step 1.\n"
        "12. On failure: append a timestamped failure note below the --- separator. "
        "If Attempts < 5, rename back to .md and loop. "
        f"If Attempts == 5, create {halt_file}, rename to .failed.md, perform halt procedure, exit."
    )

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        system_prompt=_system_prompt(),
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="acceptEdits",
        max_turns=1000,
        model=model,
    )

    async for message in query(prompt=task, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            log_usage(token_log, "junior", message.usage)
            print(f"\n\n[Junior Coding Agent finished — stop reason: {message.stop_reason}]")


if __name__ == "__main__":
    args = _parse_args()
    stories_dir = Path(args.stories_dir)
    if not stories_dir.is_absolute():
        stories_dir = PROJECT_ROOT / stories_dir
    workspace_dir = Path(args.workspace_dir)
    if not workspace_dir.is_absolute():
        workspace_dir = PROJECT_ROOT / workspace_dir
    token_log = Path(args.token_log) if args.token_log else None
    anyio.run(run, stories_dir, workspace_dir, args.model, token_log)
