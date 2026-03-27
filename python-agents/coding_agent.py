"""Coding Agent — claims and implements one story at a time from stories/."""
import anyio
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

PROJECT_ROOT = Path(__file__).parent.parent
STORIES_DIR = PROJECT_ROOT / "stories"
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
ROLES_DIR = PROJECT_ROOT / "roles"


def _system_prompt() -> str:
    return (ROLES_DIR / "coding-agent.md").read_text()


async def run() -> None:
    halt_file = STORIES_DIR / "HALT"
    if halt_file.exists():
        print("[Coding Agent] HALT file detected on startup — exiting immediately.")
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
