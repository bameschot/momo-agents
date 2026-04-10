"""Ollama Junior Coding Agent — claims and implements easy stories one at a time."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import anyio
from ollama import Message

from agent_utilities import claim_story, finalise_story, load_role, resolve_path, wait_for_workspace
from ollama_utilities import (
    CODING_TOOLS,
    DEFAULT_MODEL,
    ToolExecutor,
    add_ollama_args,
    make_client,
    run_agent_loop,
)

POLL_INTERVAL = 10  # seconds between polls when no eligible story is available


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ollama Junior Coding Agent (easy stories)")
    parser.add_argument(
        "--stories-dir",
        default="",
        help="Directory containing story files (default: <workspace-dir>/stories)",
    )
    parser.add_argument(
        "--workspace-dir",
        default="workspace",
        help="Path to the workspace directory (default: workspace/ relative to project root)",
    )
    add_ollama_args(
        parser,
        default_model=DEFAULT_MODEL,
        default_agent_name="ollama-junior-coding-agent",
    )
    return parser.parse_args()



def _build_task(story_path: Path, workspace_dir: Path, outcome_file: Path) -> str:
    return (
        f"Story: {story_path}\n"
        f"Workspace: {workspace_dir}\n"
        f"Outcome file: {outcome_file}\n\n"
        "## Task\n"
        f"1. Use `read_file` to read `{workspace_dir}/CLAUDE.md` — note build/test/lint commands "
        "and the Agent Exclusion List (never read from or write to those paths).\n"
        f"2. Use `read_file` to read the story file at {story_path}.\n"
        "3. Use `read_file` to read the design doc(s) from the story's **Design ref** field "
        "(two paths separated by ' | ' — read whichever exist).\n"
        "4. Implement the acceptance criteria using `write_file` (new files) and "
        "`edit_file` (modifications).\n"
        "5. Run tests and linter per CLAUDE.md using the `bash` tool.\n"
        "6. Success:\n"
        f"   a. Use `write_file` to write the word `done` to `{outcome_file}`.\n"
        "   b. Stop immediately — do not perform any further tool calls.\n"
        f"7. Failure → use `write_file` to write the word `failed` to `{outcome_file}`, "
        "then stop immediately.\n\n"
        "IMPORTANT: Never rename, write, edit, or delete story files "
        "(.ready.md / .working.md / .done.md / .failed.md). "
        "Story file state transitions are managed by the pipeline harness outside the LLM session."
    )



async def run(
    stories_dir: Path,
    workspace_dir: Path,
    model: str,
    ollama_host: str,
    run_log: Path | None,
    agent_name: str,
    conv_log_dir: Path | None,
) -> None:
    pipeline_complete = workspace_dir / ".sentinels" / "pipeline_complete"

    await wait_for_workspace(workspace_dir, agent_name, POLL_INTERVAL)

    system_prompt = load_role("ollama_roles/ollama-junior-coding-agent")
    executor = ToolExecutor(workspace_dir)
    client = make_client(ollama_host)
    print(f"[{agent_name}] Connected to Ollama at {ollama_host}, model={model}", flush=True)

    while True:
        if pipeline_complete.exists():
            print(f"[{agent_name}] Pipeline complete — exiting.")
            return

        story_path = claim_story(stories_dir, ["STORY-*.easy.ready.md"])
        if story_path is None:
            print(
                f"[{agent_name}] No easy.ready stories available — "
                f"polling every {POLL_INTERVAL}s..."
            )
            await anyio.sleep(POLL_INTERVAL)
            continue

        print(f"[{agent_name}] Claimed {story_path.name} — starting fresh session.", flush=True)
        story_id = story_path.stem.split(".")[0]  # e.g. STORY-001
        outcome_file = workspace_dir / ".sentinels" / f"{story_id}.outcome"
        task = _build_task(story_path, workspace_dir, outcome_file)

        messages: list[Message] = [Message(role="user", content=task)]
        await run_agent_loop(
            messages=messages,
            client=client,
            model=model,
            tools=CODING_TOOLS,
            executor=executor,
            agent_name=agent_name,
            system_prompt=system_prompt,
            conv_log_dir=conv_log_dir,
            context=story_id,
        )

        finalise_story(story_path, outcome_file, run_log, agent_name)


if __name__ == "__main__":
    args = _parse_args()
    workspace_dir = resolve_path(args.workspace_dir)
    stories_dir = resolve_path(args.stories_dir) if args.stories_dir else workspace_dir / "stories"
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(
        run,
        stories_dir,
        workspace_dir,
        args.model,
        args.ollama_host,
        run_log,
        args.agent_name,
        conv_log_dir,
    )
