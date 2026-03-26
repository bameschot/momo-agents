"""Story Reviewer Agent — triages .failed.md stories with the user and resets them."""
import anyio
import sys
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

PROJECT_ROOT = Path(__file__).parent.parent
STORIES_DIR = PROJECT_ROOT / "stories"
ROLES_DIR = PROJECT_ROOT / "roles"


def _system_prompt() -> str:
    return (ROLES_DIR / "story-reviewer.md").read_text()


async def run() -> None:
    halt_file = STORIES_DIR / "HALT"
    failed_stories = sorted(STORIES_DIR.glob("STORY-*.failed.md"))

    if not halt_file.exists():
        print("[Story Reviewer] No HALT file found — nothing to review.")
        return

    if not failed_stories:
        print("[Story Reviewer] HALT file exists but no .failed.md stories found.")
        print(f"  Removing stale HALT file: {halt_file}")
        halt_file.unlink()
        return

    print(f"[Story Reviewer] Found {len(failed_stories)} failed story(s) to review.")

    task = (
        f"Project root: {PROJECT_ROOT}\n"
        f"Stories directory: {STORIES_DIR}\n"
        f"HALT file: {halt_file}\n"
        f"Failed stories: {', '.join(s.name for s in failed_stories)}\n\n"
        "Work through each failed story one at a time:\n"
        "1. Atomically claim the next .failed.md story by renaming it to .reviewing.md.\n"
        "2. Read the full story file including all accumulated failure notes.\n"
        "3. Use AskUserQuestion to present the user with:\n"
        "   - The story title, goal, and acceptance criteria.\n"
        "   - A plain-language summary of each failed attempt and what went wrong.\n"
        "   - Options: new approach, relaxed constraints, split the story, skip it.\n"
        "4. Based on the user's guidance, rewrite the entire story file content:\n"
        "   - Reset **Attempts** to 0.\n"
        "   - Preserve **Index** and **Depends on**.\n"
        "   - Rewrite context, acceptance criteria, and hints.\n"
        "   - Remove all old failure notes.\n"
        "5. Rename .reviewing.md → .md (story re-enters the pending queue).\n"
        "6. After ALL failed stories are resolved:\n"
        f"   - Delete {halt_file}.\n"
        "   - Report to the user that the pipeline is ready to resume."
    )

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        system_prompt=_system_prompt(),
        allowed_tools=["AskUserQuestion", "Read", "Write", "Glob", "Bash"],
        permission_mode="default",
        max_turns=500,
    )

    async for message in query(prompt=task, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            print(f"\n\n[Story Reviewer Agent finished — stop reason: {message.stop_reason}]")

    # Confirm HALT was removed.
    if halt_file.exists():
        print(
            f"\nWarning: HALT file still exists at {halt_file}. "
            "The agent may not have resolved all failed stories.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    anyio.run(run)
