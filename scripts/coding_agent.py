"""Coding Agent — claims and implements one story at a time from stories/."""
import argparse
import re
import anyio
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

PROJECT_ROOT = Path(__file__).parent.parent
ROLES_DIR = PROJECT_ROOT / "roles"

POLL_INTERVAL = 60  # seconds between polls when no eligible story is available

DEFAULT_MODEL = "claude-sonnet-4-6"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Coding Agent")
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
    return parser.parse_args()


def _system_prompt() -> str:
    return (ROLES_DIR / "coding-agent.md").read_text()


def _unclaimed_stories(stories_dir: Path) -> list[Path]:
    """Return bare STORY-NNN.md files (not .working / .done / .failed / .reviewing)."""
    return [
        p for p in stories_dir.glob("STORY-*.md")
        if re.match(r"^STORY-\d+\.md$", p.name)
    ]


def _in_progress_stories(stories_dir: Path) -> list[Path]:
    """Return stories currently being worked on by any agent."""
    return list(stories_dir.glob("STORY-*.working.md"))


async def _wait_for_eligible_story(stories_dir: Path, pipeline_complete: Path) -> bool:
    """
    Poll until at least one unclaimed story exists, then return True.
    Keeps polling indefinitely — even when all current stories are done —
    so new stories written by the BA agent are picked up automatically.
    Returns False only when a HALT is detected or the pipeline_complete
    sentinel is written by the orchestrator.
    """
    halt_file = stories_dir / "HALT"
    last_status = ""
    while True:
        if halt_file.exists():
            print("[Coding Agent] HALT detected while waiting — exiting.")
            return False

        if pipeline_complete.exists():
            print("[Coding Agent] Pipeline complete sentinel detected — exiting.")
            return False

        unclaimed = _unclaimed_stories(stories_dir)
        if unclaimed:
            return True  # At least one story ready to claim

        in_progress = _in_progress_stories(stories_dir)
        status = f"in-progress={len(in_progress)}" if in_progress else "all done"
        if status != last_status:
            print(
                f"[Coding Agent] No unclaimed story available ({status}). "
                f"Polling every {POLL_INTERVAL}s for new stories..."
            )
            last_status = status

        await anyio.sleep(POLL_INTERVAL)


async def run(stories_dir: Path, workspace_dir: Path, model: str) -> None:
    pipeline_complete = PROJECT_ROOT / ".sentinels" / "pipeline_complete"
    halt_file = stories_dir / "HALT"

    if halt_file.exists():
        print("[Coding Agent] HALT file detected on startup — exiting immediately.")
        return

    # Wait until an eligible story is available before engaging the LLM
    if not await _wait_for_eligible_story(stories_dir, pipeline_complete):
        print("[Coding Agent] No stories to process — exiting.")
        return

    task = (
        f"Project root: {PROJECT_ROOT}\n"
        f"Stories directory: {stories_dir}\n"
        f"Workspace directory: {workspace_dir}\n\n"
        "Begin the coding agent loop now:\n"
        f"1. Check for {halt_file} — exit immediately if it exists.\n"
        f"2. Scan {stories_dir} for pending stories (STORY-*.md, not .working/.done/.failed/.reviewing).\n"
        "3. Sort candidates by the **Index** field (ascending). For each candidate, check "
        "**Depends on** and skip if the dependency is not yet .done.md.\n"
        "4. Atomically claim the lowest-index eligible story by renaming "
        "STORY-NNN.md → STORY-NNN.working.md. If the rename fails (another agent claimed "
        "it first), try the next candidate. If no story can be claimed, exit.\n"
        f"5. Read {workspace_dir}/CLAUDE.md for build, test, and lint instructions.\n"
        "6. Increment **Attempts** in the story file header.\n"
        "7. Implement the story's acceptance criteria inside the workspace directory.\n"
        "8. Run tests and linter as instructed in CLAUDE.md.\n"
        f"9. Before committing, check for {halt_file} again — if found, perform the "
        "halt procedure (discard uncommitted changes, rename .working.md back to .md, exit).\n"
        "10. On success: rename .working.md → .done.md, commit workspace changes, loop to step 1.\n"
        "11. On failure: append a timestamped failure note below the --- separator. "
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
            print(f"\n\n[Coding Agent finished — stop reason: {message.stop_reason}]")


if __name__ == "__main__":
    args = _parse_args()
    stories_dir = Path(args.stories_dir)
    if not stories_dir.is_absolute():
        stories_dir = PROJECT_ROOT / stories_dir
    workspace_dir = Path(args.workspace_dir)
    if not workspace_dir.is_absolute():
        workspace_dir = PROJECT_ROOT / workspace_dir
    anyio.run(run, stories_dir, workspace_dir, args.model)
