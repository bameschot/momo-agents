"""Ollama Designer Agent — interactive multi-turn Q&A that produces workspace/design/<feature>.new.md."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory (agent_utilities, token_logger).
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import anyio
from ollama import Message

from agent_utilities import append_run_log, load_role, resolve_path
from ollama_utilities import (
    DEFAULT_MODEL,
    DESIGNER_TOOLS,
    ToolExecutor,
    add_ollama_args,
    make_client,
    run_chat_loop,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ollama Designer Agent")
    parser.add_argument(
        "--workspace-dir",
        default="workspace",
        help="Path to the workspace directory (default: workspace/ relative to project root)",
    )
    add_ollama_args(
        parser,
        default_model=DEFAULT_MODEL,
        default_agent_name="ollama-designer",
    )
    return parser.parse_args()


def _initial_prompt(design_dir: Path) -> str:
    return (
        f"Design output directory: {design_dir}\n\n"
        "Begin the design session. Greet the user and ask what they want to build. "
        "Ask clarifying questions freely until you have a complete, unambiguous picture "
        "of the requirements.\n\n"
        "File naming rules:\n"
        f"- Always save designs as {design_dir}/<feature-name>.new.md, where <feature-name> "
        "is a short kebab-case identifier derived from what is being designed.\n"
        f"- If {design_dir}/<feature-name>.processed.md already exists (an earlier version "
        "was processed by the Business Analyst), still write to <feature-name>.new.md — "
        "this signals the BA to re-process the updated design.\n"
        "- Never write to <feature-name>.processed.md directly.\n\n"
        "When the user says 'write', produce and save the design document using the "
        "write_file tool following the format defined in your role."
    )


async def run(
    workspace_dir: Path,
    model: str,
    ollama_host: str,
    tokens_log_dir: Path | None,
    run_log: Path | None,
    agent_name: str,
    conv_log_dir: Path | None,
) -> None:
    token_log = tokens_log_dir / f"{agent_name}.jsonl" if tokens_log_dir else None

    design_dir = workspace_dir / "design"
    design_dir.mkdir(parents=True, exist_ok=True)

    executor = ToolExecutor(workspace_dir)
    client = make_client(ollama_host)
    print(f"[{agent_name}] Connected to Ollama at {ollama_host}, model={model}", flush=True)

    before = set(design_dir.glob("*.new.md"))
    messages: list[Message] = [Message(role="user", content=_initial_prompt(design_dir))]

    await run_chat_loop(
        messages=messages,
        client=client,
        model=model,
        tools=DESIGNER_TOOLS,
        executor=executor,
        agent_name=agent_name,
        token_log=token_log,
        system_prompt=load_role("ollama_roles/ollama-designer"),
        exit_phrases=("exit", "quit", "bye", "done"),
        conv_log_dir=conv_log_dir,
        context="design",
    )

    after = set(design_dir.glob("*.new.md"))
    for new_file in sorted(after - before, key=lambda p: p.name):
        append_run_log(run_log, agent_name, f"design written: {new_file.name}")
        print(
            f"\n[Design saved: {new_file.name}]\n"
            "[The Business Analyst will pick it up automatically.]",
            flush=True,
        )


if __name__ == "__main__":
    args = _parse_args()
    workspace_dir = resolve_path(args.workspace_dir)
    tokens_log_dir = Path(args.tokens_log_dir) if args.tokens_log_dir else None
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(
        run,
        workspace_dir,
        args.model,
        args.ollama_host,
        tokens_log_dir,
        run_log,
        args.agent_name,
        conv_log_dir,
    )
