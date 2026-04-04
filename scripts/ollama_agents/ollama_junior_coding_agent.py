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


def _build_task(story_path: Path, workspace_dir: Path, claude_md: str, halt_file: Path) -> str:
    return (
        f"Story: {story_path}\n"
        f"Workspace: {workspace_dir}\n"
        f"HALT file: {halt_file}\n\n"
        f"## workspace/CLAUDE.md\n\n{claude_md}\n\n"
        "## Task\n"
        "1. Read the story file.\n"
        "2. Read the design doc(s) from the story's **Design ref** field "
        "(two paths separated by ' | ' — read whichever exist).\n"
        "3. Note the '## Agent Exclusion List' in CLAUDE.md above — never read from or "
        "write to those paths.\n"
        "4. Implement the acceptance criteria.\n"
        "5. Run tests and linter per CLAUDE.md.\n"
        f"6. Check {halt_file} — if found, perform the halt procedure.\n"
        "7. Success → rename .easy.working.md → .easy.done.md, commit.\n"
        f"8. Failure → create {halt_file}, rename .easy.working.md → "
        ".easy.failed.md, perform halt procedure."
    )


async def run(
    stories_dir: Path,
    workspace_dir: Path,
    model: str,
    ollama_host: str,
    tokens_log_dir: Path | None,
    run_log: Path | None,
    agent_name: str,
) -> None:
    token_log = tokens_log_dir / f"{agent_name}.jsonl" if tokens_log_dir else None
    pipeline_complete = workspace_dir / ".sentinels" / "pipeline_complete"
    halt_file = stories_dir / "HALT"

    await wait_for_workspace(workspace_dir, agent_name, POLL_INTERVAL)

    claude_md = (workspace_dir / "CLAUDE.md").read_text()
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
        task = _build_task(story_path, workspace_dir, claude_md, halt_file)

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
            continuation_prompt=(
                "Continue implementing the story. Use the available tools to make progress. "
                "When all acceptance criteria are met and tests pass, rename the story file "
                "from .working.md to .done.md and commit. "
                "If the implementation cannot succeed, create the HALT file, rename to .failed.md, "
                "and perform the halt procedure. Do not describe what you plan to do — use tools directly."
            ),
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
    anyio.run(
        run,
        stories_dir,
        workspace_dir,
        args.model,
        args.ollama_host,
        tokens_log_dir,
        run_log,
        args.agent_name,
    )
