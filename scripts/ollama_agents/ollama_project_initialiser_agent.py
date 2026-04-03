"""Ollama Project Initialiser Agent — scaffolds workspace/ from a design document."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory (agent_utilities, token_logger).
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import anyio
from ollama import Message

from agent_utilities import append_run_log, load_role, resolve_path
from ollama_utilities import (
    CODING_TOOLS,
    DEFAULT_MODEL,
    ToolExecutor,
    add_ollama_args,
    make_client,
    run_agent_loop,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ollama Project Initialiser Agent")
    parser.add_argument(
        "--design",
        required=True,
        help="Path to the design document (e.g. workspace/design/my-feature.new.md)",
    )
    parser.add_argument(
        "--workspace-dir",
        default="workspace",
        help="Path to the workspace directory (default: workspace/ relative to project root)",
    )
    add_ollama_args(
        parser,
        default_model=DEFAULT_MODEL,
        default_agent_name="ollama-project-initialiser",
    )
    return parser.parse_args()


def _build_task(design_path: Path, workspace_dir: Path) -> str:
    return (
        f"Workspace: {workspace_dir}\n"
        f"Design document: {design_path}\n\n"
        "Read the design document in full. Then:\n"
        f"1. Create {workspace_dir}/CLAUDE.md with build, test, and lint commands "
        "appropriate for the technology stack described in the design.\n"
        "2. Scaffold the initial project structure inside the workspace directory: "
        "directory layout, configuration files, empty entry points, and dependency "
        "manifests with required packages listed.\n"
        "Do not implement any story logic — only the skeleton that lets Coding Agents "
        "start implementing immediately."
    )


async def run(
    design_path: Path,
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

    executor = ToolExecutor(workspace_dir)
    client = make_client(ollama_host)
    print(f"[{agent_name}] Connected to Ollama at {ollama_host}, model={model}", flush=True)

    task = _build_task(design_path, workspace_dir)
    messages: list[Message] = [Message(role="user", content=task)]

    await run_agent_loop(
        messages=messages,
        client=client,
        model=model,
        tools=CODING_TOOLS,
        executor=executor,
        agent_name=agent_name,
        token_log=token_log,
        system_prompt=load_role("ollama-project-initialiser"),
    )

    append_run_log(run_log, agent_name, f"project initiated from: {design_path.name}")
    print(f"[{agent_name}] Done.", flush=True)


if __name__ == "__main__":
    args = _parse_args()
    design_path = resolve_path(args.design)
    workspace_dir = resolve_path(args.workspace_dir)
    tokens_log_dir = Path(args.tokens_log_dir) if args.tokens_log_dir else None
    run_log = Path(args.run_log) if args.run_log else None
    anyio.run(
        run,
        design_path,
        workspace_dir,
        args.model,
        args.ollama_host,
        tokens_log_dir,
        run_log,
        args.agent_name,
    )
