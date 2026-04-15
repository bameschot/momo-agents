"""Ollama Project Initialiser Agent — scaffolds workspace/ from a design document."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import anyio
from ollama import Message

from agent_utilities import append_run_log, load_role, resolve_path
from ollama_utilities import (
    CODING_TOOLS,
    DEFAULT_MODEL,
    ToolExecutor,
    build_ollama_arg_parser,
    make_client,
    run_agent_loop,
)


def _parse_args():
    parser = build_ollama_arg_parser(
        description="Ollama Project Initialiser Agent",
        default_model=DEFAULT_MODEL,
        default_agent_name="ollama-project-initialiser",
    )
    parser.add_argument(
        "--design",
        required=True,
        help="Path to the design document (e.g. workspace/design/my-feature.new.md)",
    )
    return parser.parse_args()


def _build_task(design_path: Path, workspace_dir: Path) -> str:
    return (
        f"Workspace: {workspace_dir}\n"
        f"Design document: {design_path}\n\n"
        "Read the design document in full. Then follow this workflow exactly using the `bash` tool:\n\n"
        "**Scaffolding**:\n"
        f"1. Create {workspace_dir}/CLAUDE.md with build, test, and lint commands "
        "appropriate for the technology stack described in the design.\n"
        "2. Scaffold the initial project structure inside the workspace directory: "
        "directory layout, configuration files, empty entry points, and dependency "
        "manifests with required packages listed. "
        "Always ensure `.sentinels/` is listed in `.gitignore`.\n"
        "3. After all files are written, perform an initial commit: "
        "use the `bash` tool to run `git add -A` then `git commit -m \"chore: initial project scaffold\"`.\n"
        "Do not implement any story logic — only the skeleton that lets Coding Agents "
        "start implementing immediately.\n\n"
        "After the initial commit is complete, stop immediately.\n"
    )


async def run(
    design_path: Path,
    workspace_dir: Path,
    model: str,
    ollama_host: str,
    run_log: Path | None,
    agent_name: str,
    conv_log_dir: Path | None,
) -> None:
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
        system_prompt=load_role("ollama_roles/ollama-project-initialiser"),
        conv_log_dir=conv_log_dir,
        context="project-init",
    )

    append_run_log(run_log, agent_name, f"project initiated from: {design_path.name}")
    print(f"[{agent_name}] Done.", flush=True)


if __name__ == "__main__":
    args = _parse_args()
    design_path = resolve_path(args.design)
    workspace_dir = resolve_path(args.workspace_dir)
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(
        run,
        design_path,
        workspace_dir,
        args.model,
        args.ollama_host,
        run_log,
        args.agent_name,
        conv_log_dir,
    )
