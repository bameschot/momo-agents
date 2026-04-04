"""Ollama Business Analyst Agent — reads a design document and writes story files."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory (agent_utilities, token_logger).
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import anyio
from ollama import Message

from agent_utilities import append_run_log, load_role, resolve_path, wait_for_workspace
from ollama_utilities import (
    ANALYST_TOOLS,
    DEFAULT_MODEL,
    ToolExecutor,
    add_ollama_args,
    make_client,
    run_agent_loop,
)

POLL_INTERVAL = 10  # seconds between polls while waiting for workspace/CLAUDE.md


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ollama Business Analyst Agent")
    parser.add_argument(
        "--design",
        required=True,
        help="Path to the design document (e.g. workspace/design/my-feature.new.md)",
    )
    parser.add_argument(
        "--stories-dir",
        default="",
        help="Directory where story files are written (default: <workspace-dir>/stories)",
    )
    parser.add_argument(
        "--workspace-dir",
        default="workspace",
        help="Path to the workspace directory (default: workspace/ relative to project root)",
    )
    add_ollama_args(
        parser,
        default_model=DEFAULT_MODEL,
        default_agent_name="ollama-business-analyst",
    )
    return parser.parse_args()


def _build_task(
    design_path: Path,
    stories_dir: Path,
    workspace_dir: Path,
    next_index: int,
) -> str:
    return (
        f"Project root: {workspace_dir}\n"
        f"Design document: {design_path}\n"
        f"Stories output directory: {stories_dir}\n"
        f"Next story number to use: {next_index:03d} (zero-padded three digits)\n\n"
        "Read the design document in full. Decompose it into an ordered set of discrete, "
        "implementable stories and write each one to the stories directory as STORY-NNN.md. "
        "Follow the story file format defined in your role exactly.\n\n"
        "Complexity rules (mandatory):\n"
        "- Assign every story a complexity of easy, medium, or hard.\n"
        "- Include the complexity label in both the heading and the **Complexity** field.\n"
        "- Strongly prefer easy (~3 hours) and medium (~6 hours) stories. Split any hard story "
        "into smaller pieces unless doing so would make the resulting stories incoherent or "
        "non-implementable on their own.\n\n"
        "Do not leave open questions — resolve ambiguities from the design before writing."
    )


async def run(
    design_path: Path,
    stories_dir: Path,
    workspace_dir: Path,
    model: str,
    ollama_host: str,
    tokens_log_dir: Path | None,
    run_log: Path | None,
    agent_name: str,
) -> None:
    token_log = tokens_log_dir / f"{agent_name}.jsonl" if tokens_log_dir else None

    if not design_path.exists():
        print(f"Error: design file not found: {design_path}", file=sys.stderr)
        sys.exit(1)

    await wait_for_workspace(workspace_dir, agent_name, POLL_INTERVAL)

    stories_dir.mkdir(parents=True, exist_ok=True)
    next_index = len(list(stories_dir.glob("STORY-*.md"))) + 1

    executor = ToolExecutor(workspace_dir)
    client = make_client(ollama_host)
    print(f"[{agent_name}] Connected to Ollama at {ollama_host}, model={model}", flush=True)

    task = _build_task(design_path, stories_dir, workspace_dir, next_index)
    before = set(stories_dir.glob("STORY-*.md"))

    messages: list[Message] = [Message(role="user", content=task)]
    await run_agent_loop(
        messages=messages,
        client=client,
        model=model,
        tools=ANALYST_TOOLS,
        executor=executor,
        agent_name=agent_name,
        token_log=token_log,
        system_prompt=load_role("ollama_roles/ollama-business-analyst"),
        continuation_prompt=(
            f"Continue writing the story files to {stories_dir}. "
            f"Each story must be a separate file named STORY-NNN.md (zero-padded three digits). "
            f"Do not describe what you plan to do — call write_file directly for each story."
        ),
    )

    after = set(stories_dir.glob("STORY-*.md"))
    for story_file in sorted(after - before, key=lambda p: p.name):
        append_run_log(run_log, agent_name, f"story created: {story_file.name}")
        print(f"[{agent_name}] Created: {story_file.name}", flush=True)

    if design_path.name.endswith(".new.md"):
        processed_path = design_path.with_name(design_path.name.replace(".new.md", ".processed.md"))
        design_path.rename(processed_path)
        print(f"[{agent_name}] Design marked as processed: {processed_path.name}", flush=True)
        append_run_log(run_log, agent_name, f"design processed: {processed_path.name}")


if __name__ == "__main__":
    args = _parse_args()
    design_path = resolve_path(args.design)
    workspace_dir = resolve_path(args.workspace_dir)
    stories_dir = resolve_path(args.stories_dir) if args.stories_dir else workspace_dir / "stories"
    tokens_log_dir = Path(args.tokens_log_dir) if args.tokens_log_dir else None
    run_log = Path(args.run_log) if args.run_log else None
    anyio.run(
        run,
        design_path,
        stories_dir,
        workspace_dir,
        args.model,
        args.ollama_host,
        tokens_log_dir,
        run_log,
        args.agent_name,
    )
