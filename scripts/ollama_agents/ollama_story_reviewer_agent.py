"""Ollama Story Reviewer Agent — triages .failed.md stories with the user and resets them."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import anyio
from ollama import Message

from agent_utilities import PROJECT_ROOT, load_role, resolve_path
from ollama_utilities import (
    DEFAULT_MODEL,
    REVIEWER_TOOLS,
    ToolExecutor,
    add_ollama_args,
    make_client,
    run_agent_loop,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ollama Story Reviewer Agent")
    parser.add_argument(
        "--stories-dir",
        default=str(PROJECT_ROOT / "workspace" / "stories"),
        help="Directory containing story files (default: <project-root>/workspace/stories)",
    )
    add_ollama_args(
        parser,
        default_model=DEFAULT_MODEL,
        default_agent_name="ollama-story-reviewer",
    )
    return parser.parse_args()


def _build_task(stories_dir: Path, halt_file: Path, failed_stories: list[Path]) -> str:
    return (
        f"Project root: {stories_dir.parent}\n"
        f"Stories directory: {stories_dir}\n"
        f"HALT file: {halt_file}\n"
        f"Failed stories: {', '.join(s.name for s in failed_stories)}\n\n"
        "Story filenames follow the pattern STORY-NNN.[complexity].[state].md.\n\n"
        "Work through each failed story one at a time:\n"
        "1. Atomically claim the next .failed.md story by renaming it to .reviewing.md "
        "(preserve the complexity segment, e.g. STORY-001.easy.failed.md → "
        "STORY-001.easy.reviewing.md) — use the `bash` tool with shell command "
        f"`mv <story>.failed.md <story>.reviewing.md` (absolute paths under {stories_dir}).\n"
        "2. Use `read_file` to read the full story file including all accumulated failure notes.\n"
        "3. Use the `ask_user` tool to present the user with:\n"
        "   - The story title, goal, and acceptance criteria.\n"
        "   - A plain-language summary of each failed attempt and what went wrong.\n"
        "   - Options: new approach, relaxed constraints, split the story, skip it.\n"
        "4. Based on the user's guidance, use `write_file` to rewrite the entire story file "
        "over the .reviewing.md path:\n"
        "   - Preserve **Index** and **Depends on**.\n"
        "   - Rewrite context, acceptance criteria, and hints.\n"
        "   - Remove all old failure notes.\n"
        "5. Return the story to the unprocessed queue — use the `bash` tool with shell command "
        f"`mv <story>.reviewing.md <bare-story>.md` (strip complexity and state, e.g. "
        "STORY-001.easy.reviewing.md → STORY-001.md, absolute paths under "
        f"{stories_dir}).\n"
        "6. After ALL failed stories are resolved:\n"
        f"   - Use the `bash` tool with shell command `rm {halt_file}` to delete the HALT file.\n"
        "   - Use the `ask_user` tool to report to the user that the pipeline is ready to resume."
    )


async def run(
    stories_dir: Path,
    model: str,
    ollama_host: str,
    agent_name: str,
    conv_log_dir: Path | None,
) -> None:
    halt_file = stories_dir / "HALT"
    failed_stories = sorted(stories_dir.glob("STORY-*.failed.md"))

    if not halt_file.exists():
        print(f"[{agent_name}] No HALT file found — nothing to review.")
        return

    if not failed_stories:
        print(f"[{agent_name}] HALT file exists but no .failed.md stories found.")
        print(f"  Removing stale HALT file: {halt_file}")
        halt_file.unlink()
        return

    print(f"[{agent_name}] Found {len(failed_stories)} failed story(s) to review.", flush=True)

    executor = ToolExecutor(stories_dir.parent)
    client = make_client(ollama_host)
    print(f"[{agent_name}] Connected to Ollama at {ollama_host}, model={model}", flush=True)

    task = _build_task(stories_dir, halt_file, failed_stories)
    messages: list[Message] = [Message(role="user", content=task)]

    await run_agent_loop(
        messages=messages,
        client=client,
        model=model,
        tools=REVIEWER_TOOLS,
        executor=executor,
        agent_name=agent_name,
        max_turns=500,
        system_prompt=load_role("ollama_roles/ollama-story-reviewer"),
        conv_log_dir=conv_log_dir,
        context="review",
    )

    if halt_file.exists():
        print(
            f"\nWarning: HALT file still exists at {halt_file}. "
            "The agent may not have resolved all failed stories.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    args = _parse_args()
    stories_dir = resolve_path(args.stories_dir)
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(
        run,
        stories_dir,
        args.model,
        args.ollama_host,
        args.agent_name,
        conv_log_dir,
    )
