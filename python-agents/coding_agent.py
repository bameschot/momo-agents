"""Coding Agent — claims and implements one story at a time from stories/."""
import re
import anyio
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

PROJECT_ROOT = Path(__file__).parent.parent
STORIES_DIR = PROJECT_ROOT / "stories"
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
ROLES_DIR = PROJECT_ROOT / "roles"

POLL_INTERVAL = 10  # seconds between polls when no eligible story is available
PIPELINE_COMPLETE = PROJECT_ROOT / ".sentinels" / "pipeline_complete"


def _system_prompt() -> str:
    return (ROLES_DIR / "coding-agent.md").read_text()


def _unclaimed_stories() -> list[Path]:
    """Return bare STORY-NNN.md files (not .working / .done / .failed / .reviewing)."""
    return [
        p for p in STORIES_DIR.glob("STORY-*.md")
        if re.match(r"^STORY-\d+\.md$", p.name)
    ]


def _in_progress_stories() -> list[Path]:
    """Return stories currently being worked on by any agent."""
    return list(STORIES_DIR.glob("STORY-*.working.md"))


async def _wait_for_eligible_story(halt_file: Path) -> bool:
    """
    Poll until at least one unclaimed story exists, then return True.
    Keeps polling indefinitely — even when all current stories are done —
    so new stories written by the BA agent are picked up automatically.
    Returns False only when a HALT is detected or the pipeline_complete
    sentinel is written by the orchestrator.
    """
    last_status = ""
    while True:
        if halt_file.exists():
            print("[Coding Agent] HALT detected while waiting — exiting.")
            return False

        if PIPELINE_COMPLETE.exists():
            print("[Coding Agent] Pipeline complete sentinel detected — exiting.")
            return False

        unclaimed = _unclaimed_stories()
        if unclaimed:
            return True  # At least one story ready to claim

        in_progress = _in_progress_stories()
        status = f"in-progress={len(in_progress)}" if in_progress else "all done"
        if status != last_status:
            print(
                f"[Coding Agent] No unclaimed story available ({status}). "
                f"Polling every {POLL_INTERVAL}s for new stories..."
            )
            last_status = status

        await anyio.sleep(POLL_INTERVAL)


async def run() -> None:
    halt_file = STORIES_DIR / "HALT"

    if halt_file.exists():
        print("[Coding Agent] HALT file detected on startup — exiting immediately.")
        return

    # Wait until an eligible story is available before engaging the LLM
    if not await _wait_for_eligible_story(halt_file):
        print("[Coding Agent] No stories to process — exiting.")
        return

    task = (
        f"Project root: {PROJECT_ROOT}\n"
        f"Stories directory: {STORIES_DIR}\n"
        f"Workspace directory: {WORKSPACE_DIR}\n\n"
        "Begin the coding agent loop now:\n"
        f"1. Check for {halt_file} — exit immediately if it exists.\n"
        f"2. Scan {STORIES_DIR} for pending stories (STORY-*.md, not .working/.done/.failed/.reviewing).\n"
        "3. Sort candidates by the **Index** field (ascending). For each candidate, check "
        "**Depends on** and skip if the dependency is not yet .done.md.\n"
        "4. Atomically claim the lowest-index eligible story by renaming "
        "STORY-NNN.md → STORY-NNN.working.md. If the rename fails (another agent claimed "
        "it first), try the next candidate. If no story can be claimed, exit.\n"
        f"5. Read {WORKSPACE_DIR}/CLAUDE.md for build, test, and lint instructions.\n"
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
    )

    async for message in query(prompt=task, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            print(f"\n\n[Coding Agent finished — stop reason: {message.stop_reason}]")


if __name__ == "__main__":
    anyio.run(run)
