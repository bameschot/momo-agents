"""Merger Agent (Ollama) — merges completed story workspaces into the main branch.

Workflow per story:
  1. Python: scan .sentinels/merge-queue/ for the lowest-numbered STORY-NNN.zip.
  2. Python: unzip it to .sentinels/merge-STORY-NNN/ (isolated staging area).
  3. LLM  : create a git branch, copy staged files into the workspace, commit,
             merge back to main, write outcome sentinel.
  4. Python: on success — mark the story .done.md in workspace/stories/.
  5. Python: delete staging dir and zip from the merge-queue.

Stories are always processed in ascending STORY-NNN order.
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import anyio
from ollama import Message

from agent_utilities import (
    append_run_log,
    get_next_merge_story,
    load_role,
    mark_story_done_after_merge,
    resolve_path,
    unzip_workspace_for_merge,
    wait_for_workspace,
)
from ollama_utilities import (
    DEFAULT_MODEL,
    ToolExecutor,
    add_ollama_args,
    make_client,
    run_agent_loop,
)

POLL_INTERVAL = 10  # seconds between polls when merge-queue is empty

# Minimal tool set needed for the merger: bash for git commands, write for outcome.
MERGER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a bash command and return its stdout/stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file (creates or overwrites).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file."},
                    "content": {"type": "string", "description": "Content to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ollama Merger Agent — merges story zips into main branch")
    parser.add_argument(
        "--workspace-dir",
        default="workspace",
        help="Path to the workspace directory (default: workspace/ relative to project root)",
    )
    add_ollama_args(
        parser,
        default_model=DEFAULT_MODEL,
        default_agent_name="ollama-merger-agent",
    )
    return parser.parse_args()


def _build_task(
    story_id: str,
    extract_dir: Path,
    workspace_dir: Path,
    outcome_file: Path,
) -> str:
    branch_name = story_id.lower()  # e.g. story-003
    return (
        f"## Merge Task: {story_id}\n\n"
        f"Staged workspace (completed code to merge): {extract_dir}\n"
        f"Main workspace git repository            : {workspace_dir}\n"
        f"Outcome file                             : {outcome_file}\n\n"
        "## Steps\n\n"
        f"1. Check whether the main workspace has any commits yet:\n"
        f"   Use `bash` with: cd {workspace_dir} && git log --oneline -1\n"
        f"   If there are NO commits, create an initial commit first:\n"
        f"   Use `bash` with: cd {workspace_dir} && git add -A && git commit -m 'chore: initial workspace scaffold'\n\n"
        f"2. Create a story branch from the recorded base commit so that git can\n"
        f"   perform a true 3-way merge (preserving changes from previously merged stories).\n"
        f"   Use `bash` with:\n"
        f"   BASE=$(cat {extract_dir}/.merge-base-commit 2>/dev/null || echo '')\n"
        f"   cd {workspace_dir}\n"
        f"   if [ -n \"$BASE\" ]; then git checkout -b {branch_name} $BASE; else git checkout -b {branch_name}; fi\n\n"
        f"3. Copy all files from the staged workspace into the main workspace,\n"
        f"   then remove the base-commit helper file so it is not committed:\n"
        f"   Use `bash` with: cp -r {extract_dir}/. {workspace_dir}/ && rm -f {workspace_dir}/.merge-base-commit\n\n"
        f"4. Stage all changes:\n"
        f"   Use `bash` with: cd {workspace_dir} && git add -A\n\n"
        f"5. Check for staged changes and commit if any:\n"
        f"   Use `bash` with: cd {workspace_dir} && git diff --cached --stat\n"
        f"   If there are staged changes, use `bash` with:\n"
        f"   cd {workspace_dir} && git commit -m 'feat: implement {story_id}'\n\n"
        f"6. Switch back to the main branch:\n"
        f"   Use `bash` with: cd {workspace_dir} && git checkout main || git checkout master\n\n"
        f"7. Merge the story branch:\n"
        f"   Use `bash` with: cd {workspace_dir} && git merge {branch_name} --no-ff -m 'merge: {story_id}'\n"
        f"   If conflicts occur, resolve them preferring incoming changes from '{branch_name}' "
        f"for all src/ and tests/ paths.\n\n"
        f"8. Write the result using `write_file`:\n"
        f"   - Success: write 'done' to {outcome_file}\n"
        f"   - Failure: write 'failed\\n<brief error>' to {outcome_file}\n\n"
        "IMPORTANT: Do not delete or modify any story files in workspace/stories/. "
        "Story state transitions are handled by the pipeline harness in Python."
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
    stories_dir = workspace_dir / "stories"
    pipeline_complete = sentinels_dir / "pipeline_complete"

    await wait_for_workspace(workspace_dir, agent_name, POLL_INTERVAL)

    system_prompt = load_role("ollama_roles/ollama-merger-agent")
    # Executor rooted at workspace_dir for relative path resolution in tool calls.
    executor = ToolExecutor(workspace_dir)
    client = make_client(ollama_host)
    print(f"[{agent_name}] Connected to Ollama at {ollama_host}, model={model}", flush=True)

    while True:
        if pipeline_complete.exists():
            print(f"[{agent_name}] Pipeline complete — exiting.")
            return

        zip_path = get_next_merge_story(merge_queue_dir)
        if zip_path is None:
            print(f"[{agent_name}] Merge-queue empty — polling every {POLL_INTERVAL}s...")
            await anyio.sleep(POLL_INTERVAL)
            continue

        story_id = zip_path.stem  # STORY-NNN
        print(f"[{agent_name}] Merging {story_id} from {zip_path.name}...", flush=True)

        # ── Python: unzip to staging area ─────────────────────────────────
        extract_dir = unzip_workspace_for_merge(zip_path, sentinels_dir)
        outcome_file = sentinels_dir / f"merge-{story_id}.outcome"
        outcome_file.unlink(missing_ok=True)

        # ── LLM: git branch, copy, commit, merge ──────────────────────────
        task = _build_task(story_id, extract_dir, workspace_dir, outcome_file)
        messages: list[Message] = [Message(role="user", content=task)]
        await run_agent_loop(
            messages=messages,
            client=client,
            model=model,
            tools=MERGER_TOOLS,
            executor=executor,
            agent_name=agent_name,
            system_prompt=system_prompt,
            conv_log_dir=conv_log_dir,
            context=story_id,
        )

        # ── Python: finalise based on LLM outcome ─────────────────────────
        outcome = outcome_file.read_text().strip() if outcome_file.exists() else ""
        if outcome.startswith("done"):
            mark_story_done_after_merge(stories_dir, story_id, run_log, agent_name, orchestrator_dir)
            zip_path.unlink(missing_ok=True)
            print(f"[{agent_name}] {story_id} merged successfully.")
        else:
            reason = outcome.split("\n", 1)[1].strip() if "\n" in outcome else "(no details)"
            print(f"[{agent_name}] WARNING: merge of {story_id} failed — {reason}")
            append_run_log(run_log, agent_name, f"merge failed: {story_id} — {reason}")

        # ── Cleanup staging area and outcome file ──────────────────────────
        shutil.rmtree(str(extract_dir), ignore_errors=True)
        if outcome_file.exists():
            outcome_file.unlink(missing_ok=True)


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
