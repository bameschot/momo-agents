"""Ollama Junior Coding Agent — claims and implements easy stories one at a time."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory (agent_utilities, token_logger).
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import anyio
from ollama import Message

from agent_utilities import append_run_log, load_role, resolve_path, wait_for_workspace
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


def _claim_story(stories_dir: Path) -> Path | None:
    """Atomically claim the lowest-numbered easy .ready story.

    Renames ``STORY-NNN.easy.ready.md`` → ``STORY-NNN.easy.working.md``.
    Returns the working path on success, None if nothing could be claimed.
    """
    candidates = sorted(stories_dir.glob("STORY-*.easy.ready.md"), key=lambda p: p.name)
    for candidate in candidates:
        working = candidate.with_name(candidate.name.replace(".ready.md", ".working.md"))
        try:
            candidate.rename(working)
            return working
        except OSError:
            continue
    return None


def _build_task(story_path: Path, workspace_dir: Path, halt_file: Path) -> str:
    done_path = story_path.with_name(story_path.name.replace(".working.md", ".done.md"))
    failed_path = story_path.with_name(story_path.name.replace(".working.md", ".failed.md"))
    story_number = story_path.name.split(".")[0]  # e.g. STORY-001
    return (
        f"Story: {story_path}\n"
        f"Workspace: {workspace_dir}\n"
        f"HALT file: {halt_file}\n\n"
        "## Task\n"
        f"1. Use `read_file` to read `{workspace_dir}/CLAUDE.md` — note build/test/lint commands "
        "and the Agent Exclusion List (never read from or write to those paths).\n"
        f"2. Use `read_file` to read the story file at {story_path}.\n"
        "3. Use `read_file` to read the design doc(s) from the story's **Design ref** field "
        "(two paths separated by ' | ' — read whichever exist).\n"
        f"4. Use the `bash` tool with shell command `git checkout -b story/{story_number}` "
        "to create and switch to the story branch.\n"
        "5. Implement the acceptance criteria using `write_file` (new files) and "
        "`edit_file` (modifications).\n"
        "6. Run tests and linter per CLAUDE.md using the `bash` tool.\n"
        f"7. Use the `bash` tool with shell command "
        f"`test -f {halt_file} && echo exists || echo absent` to check for the HALT file. "
        "If found, perform the halt procedure.\n"
        "8. Success:\n"
        f"   a. Use the `bash` tool with shell command "
        f"`git add -A && git commit -m 'implement {story_number}: <title>'`.\n"
        f"   b. Use the `bash` tool with shell command "
        f"`git checkout main && git merge --no-ff story/{story_number}` "
        "(use `master` if `main` does not exist).\n"
        f"   c. Use the `bash` tool with shell command `git branch -d story/{story_number}`.\n"
        f"   d. Use the `bash` tool with shell command `mv {story_path} {done_path}`.\n"
        "   e. Stop immediately — do not perform any further tool calls.\n"
        f"9. Failure → use the `bash` tool with shell command `touch {halt_file}` to create "
        "the HALT file, use the `bash` tool with shell command `git checkout main` to switch "
        f"back to main, use the `bash` tool with shell command `mv {story_path} {failed_path}` "
        "to rename the story, append a failure note with `edit_file`, then stop immediately."
    )


async def run(
    stories_dir: Path,
    workspace_dir: Path,
    model: str,
    ollama_host: str,
    tokens_log_dir: Path | None,
    run_log: Path | None,
    agent_name: str,
    conv_log_dir: Path | None,
) -> None:
    token_log = tokens_log_dir / f"{agent_name}.jsonl" if tokens_log_dir else None

    pipeline_complete = workspace_dir / ".sentinels" / "pipeline_complete"
    halt_file = stories_dir / "HALT"

    await wait_for_workspace(workspace_dir, agent_name, POLL_INTERVAL)

    system_prompt = load_role("ollama_roles/ollama-junior-coding-agent")
    executor = ToolExecutor(workspace_dir)
    client = make_client(ollama_host)
    print(f"[{agent_name}] Connected to Ollama at {ollama_host}, model={model}", flush=True)

    while True:
        if halt_file.exists():
            print(f"[{agent_name}] HALT detected — exiting.")
            return
        if pipeline_complete.exists():
            print(f"[{agent_name}] Pipeline complete — exiting.")
            return

        story_path = _claim_story(stories_dir)
        if story_path is None:
            print(
                f"[{agent_name}] No easy.ready stories available — "
                f"polling every {POLL_INTERVAL}s..."
            )
            await anyio.sleep(POLL_INTERVAL)
            continue

        print(f"[{agent_name}] Claimed {story_path.name} — starting fresh session.", flush=True)
        task = _build_task(story_path, workspace_dir, halt_file)
        story_context = story_path.stem.split(".")[0]  # e.g. STORY-001

        messages: list[Message] = [Message(role="user", content=task)]
        await run_agent_loop(
            messages=messages,
            client=client,
            model=model,
            tools=CODING_TOOLS,
            executor=executor,
            agent_name=agent_name,
            token_log=token_log,
            system_prompt=system_prompt,
            conv_log_dir=conv_log_dir,
            context=story_context,
        )

        stem = story_path.name.replace(".working.md", "")
        done_path = story_path.with_name(stem + ".done.md")
        failed_path = story_path.with_name(stem + ".failed.md")
        if done_path.exists():
            append_run_log(run_log, agent_name, f"story done: {done_path.name}")
        elif failed_path.exists():
            append_run_log(run_log, agent_name, f"story failed: {failed_path.name}")


if __name__ == "__main__":
    args = _parse_args()
    workspace_dir = resolve_path(args.workspace_dir)
    stories_dir = resolve_path(args.stories_dir) if args.stories_dir else workspace_dir / "stories"
    tokens_log_dir = Path(args.tokens_log_dir) if args.tokens_log_dir else None
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(
        run,
        stories_dir,
        workspace_dir,
        args.model,
        args.ollama_host,
        tokens_log_dir,
        run_log,
        args.agent_name,
        conv_log_dir,
    )
