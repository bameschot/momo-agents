"""Ollama Junior Coding Agent — claims and implements easy stories one at a time.

Each story is worked on inside an isolated copy of the workspace so that
parallel agents never interfere with each other's file trees.  When the LLM
reports success the temp workspace is zipped into the merge-queue; the Merger
Agent then commits and merges the changes in story order.  Failed or reset
stories are handled the same as before (finalise_story handles the rename).
"""
import shutil
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import anyio
from ollama import Message

from agent_utilities import (
    append_run_log,
    claim_story,
    copy_workspace_for_story,
    finalise_story,
    get_story_id,
    load_role,
    resolve_path,
    wait_for_workspace,
    zip_workspace_for_merge,
)
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
        "7. Failure:\n"
        f"   a. Use `read_file` to read the story file at {story_path}, then use `write_file` "
        f"to write it back with a '## Failure Reasons' section appended at the very end. "
        f"Include a concise description of what went wrong: which tests or lint checks failed, "
        f"relevant error messages, and what was attempted.\n"
        f"   b. Use `write_file` to write the word `failed` to `{outcome_file}`.\n"
        "   c. Stop immediately — do not perform any further tool calls.\n\n"
        "IMPORTANT: Never rename, delete, or change the file extension of story files "
        "(.ready.md / .working.md / .done.md / .failed.md) — "
        "story file state transitions are managed by the pipeline harness outside the LLM session. "
        "The only permitted edit to a story file is appending a '## Failure Reasons' section when a story fails."
    )


async def run(
    workspace_dir: Path,
    model: str,
    ollama_host: str,
    run_log: Path | None,
    agent_name: str,
    conv_log_dir: Path | None,
) -> None:
    sentinels_dir = workspace_dir / ".sentinels"
    orchestrator_dir = sentinels_dir / "story-orchestrator"
    merge_queue_dir = sentinels_dir / "merge-queue"
    pipeline_complete = sentinels_dir / "pipeline_complete"

    await wait_for_workspace(workspace_dir, agent_name, POLL_INTERVAL)

    system_prompt = load_role("ollama_roles/ollama-junior-coding-agent")
    client = make_client(ollama_host)
    print(f"[{agent_name}] Connected to Ollama at {ollama_host}, model={model}", flush=True)

    while True:
        if pipeline_complete.exists():
            print(f"[{agent_name}] Pipeline complete — exiting.")
            return

        story_path = claim_story(orchestrator_dir, ["STORY-*.easy.ready.md"])
        if story_path is None:
            print(
                f"[{agent_name}] No easy.ready stories available — "
                f"polling every {POLL_INTERVAL}s..."
            )
            await anyio.sleep(POLL_INTERVAL)
            continue

        story_id = get_story_id(story_path)
        print(f"[{agent_name}] Claimed {story_path.name} — copying workspace to temp/{story_id}...", flush=True)

        # ── Isolate: copy workspace into a temp directory ──────────────────
        temp_workspace = copy_workspace_for_story(workspace_dir, sentinels_dir, story_id)
        temp_story_path = temp_workspace / "stories" / story_path.name
        # The orchestrator dir is excluded from the workspace copy; place the
        # story file explicitly so the LLM can read it at the expected path.
        shutil.copy2(str(story_path), str(temp_story_path))
        temp_outcome_file = sentinels_dir / f"{story_id}.outcome"

        print(f"[{agent_name}] Starting session in isolated workspace {temp_workspace}...", flush=True)

        executor = ToolExecutor(temp_workspace, allowed_absolute_paths=[temp_outcome_file])
        task = _build_task(temp_story_path, temp_workspace, temp_outcome_file)

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

        # ── Post-session: dispatch based on outcome ────────────────────────
        outcome = temp_outcome_file.read_text().strip() if temp_outcome_file.exists() else ""

        if outcome == "done":
            # Zip temp workspace → merge-queue; leave main story as .working
            zip_workspace_for_merge(temp_workspace, story_id, merge_queue_dir)
            append_run_log(run_log, agent_name, f"story queued for merge: {story_id}")
            print(f"[{agent_name}] {story_id} done — queued for merge.")
            temp_outcome_file.unlink(missing_ok=True)
        else:
            # For failed / no-outcome: copy updated story file back to the orchestrator dir
            # so failure reasons written by the LLM are preserved, then finalise.
            if temp_story_path.exists():
                shutil.copy2(str(temp_story_path), str(story_path))
            finalise_story(story_path, temp_outcome_file, run_log, agent_name)

        # ── Cleanup temp workspace ─────────────────────────────────────────
        shutil.rmtree(str(temp_workspace), ignore_errors=True)


if __name__ == "__main__":
    args = _parse_args()
    workspace_dir = resolve_path(args.workspace_dir)
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(
        run,
        workspace_dir,
        args.model,
        args.ollama_host,
        run_log,
        args.agent_name,
        conv_log_dir,
    )
