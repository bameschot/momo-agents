"""Ollama Business Analyst Agent — reads a design document and writes story files."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import anyio
from ollama import Message

from agent_utilities import append_run_log, load_role, resolve_path, wait_for_workspace
from ollama_utilities import (
    BA_TOOLS,
    DEFAULT_MODEL,
    ToolExecutor,
    add_ollama_args,
    make_client,
    run_agent_loop,
)

POLL_INTERVAL = 10  # seconds between polls while waiting for workspace/CLAUDE.md
DESIGN_POLL_INTERVAL = 10  # seconds between polls while watching for new designs


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ollama Business Analyst Agent")
    parser.add_argument(
        "--design-dir",
        default="",
        help="Directory to watch for *.new.md design files (default: <workspace-dir>/design)",
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


def _design_stem(design_path: Path) -> str:
    """Return a git-safe stem derived from the design file name."""
    name = design_path.name
    for suffix in (".new.md", ".processed.md", ".md"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name


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
        "Follow the story file format and all rules defined in your role exactly.\n\n"
        "Write story files for each story in the design, starting at the next story number provided above. "
        "Do NOT re-create or overwrite stories that already exist under any state suffix "
        "(e.g. STORY-NNN.ready.md, STORY-NNN.working.md, STORY-NNN.done.md, STORY-NNN.failed.md).\n"
    )


async def run(
    design_path: Path,
    stories_dir: Path,
    workspace_dir: Path,
    model: str,
    ollama_host: str,
    run_log: Path | None,
    agent_name: str,
    conv_log_dir: Path | None,
) -> None:
    if not design_path.exists():
        print(f"[{agent_name}] Design file no longer exists (already processed?): {design_path}", flush=True)
        return

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
        tools=BA_TOOLS,
        executor=executor,
        agent_name=agent_name,
        system_prompt=load_role("ollama_roles/ollama-business-analyst"),
        conv_log_dir=conv_log_dir,
        context="business-analysis",
    )

    after = set(stories_dir.glob("STORY-*.md"))
    for story_file in sorted(after - before, key=lambda p: p.name):
        append_run_log(run_log, agent_name, f"story created: {story_file.name}")
        print(f"[{agent_name}] Created: {story_file.name}", flush=True)

    if design_path.name.endswith(".new.md") and design_path.exists():
        processed_path = design_path.with_name(design_path.name.replace(".new.md", ".processed.md"))
        design_path.rename(processed_path)
        print(f"[{agent_name}] Design marked as processed: {processed_path.name}", flush=True)
        append_run_log(run_log, agent_name, f"design processed: {processed_path.name}")


async def watch_and_run(
    design_dir: Path,
    stories_dir: Path,
    workspace_dir: Path,
    model: str,
    ollama_host: str,
    run_log: Path | None,
    agent_name: str,
    conv_log_dir: Path | None,
) -> None:
    await wait_for_workspace(workspace_dir, agent_name, POLL_INTERVAL)
    print(f"[{agent_name}] Watching {design_dir}/ for *.new.md files...", flush=True)

    while True:
        for design_path in sorted(design_dir.glob("*.new.md")):
            feature = _design_stem(design_path)
            print(f"[{agent_name}] New design: {feature} — decomposing into stories...", flush=True)
            await run(design_path, stories_dir, workspace_dir, model, ollama_host, run_log, agent_name, conv_log_dir)
            print(f"[{agent_name}] {feature} → done. Resuming watch...", flush=True)

        await anyio.sleep(DESIGN_POLL_INTERVAL)


if __name__ == "__main__":
    args = _parse_args()
    workspace_dir = resolve_path(args.workspace_dir)
    design_dir = resolve_path(args.design_dir) if args.design_dir else workspace_dir / "design"
    stories_dir = resolve_path(args.stories_dir) if args.stories_dir else workspace_dir / "stories"
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(
        watch_and_run,
        design_dir,
        stories_dir,
        workspace_dir,
        args.model,
        args.ollama_host,
        run_log,
        args.agent_name,
        conv_log_dir,
    )
