"""Designer Agent — interactive multi-turn Q&A session that produces design/<feature>.new.md."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import anyio

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

from agent_utilities import PROJECT_ROOT, append_run_log, load_role, resolve_path
from conversation_logger import log_claude_message

DEFAULT_MODEL = "claude-sonnet-4-6"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Designer Agent")
    parser.add_argument(
        "--workspace-dir",
        default="workspace",
        help="Path to the workspace directory (default: workspace/ relative to project root)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--run-log",
        default="",
        help="Path to run-log.json file for pipeline event logging (optional)",
    )
    parser.add_argument(
        "--agent-name",
        default="designer",
        help="Name used to identify this agent in logs (default: designer)",
    )
    parser.add_argument(
        "--conv-log-dir",
        default="",
        help="Directory for per-agent conversation JSONL logs; file named <agent-name>_log.jsonl (optional)",
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
        "When the user says 'write', produce and save the design document using these rules."
    )


async def _stream_response(
    client: ClaudeSDKClient,
    conv_log_dir: Path | None,
    agent_name: str,
    context: str,
) -> tuple[str | None, dict | None]:
    """Stream and print the agent's response. Returns (stop_reason, usage)."""
    stop_reason = None
    usage = None
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            stop_reason = message.stop_reason
            usage = message.usage
        log_claude_message(conv_log_dir, agent_name, message, context)
    return stop_reason, usage


async def run(workspace_dir: Path, model: str, run_log: Path | None, agent_name: str, conv_log_dir: Path | None) -> None:
    design_dir = workspace_dir / "design"
    design_dir.mkdir(parents=True, exist_ok=True)

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        system_prompt=load_role("claude_roles/claude_designer"),
        allowed_tools=["Read", "Write"],
        permission_mode="acceptEdits",
        max_turns=50,
        model=model,
    )

    async with ClaudeSDKClient(options=options) as client:
        # Initial greeting turn
        await client.query(_initial_prompt(design_dir))
        await _stream_response(client, conv_log_dir, agent_name, "design")
        print()  # newline after agent response

        # Conversation loop — user drives each turn
        while True:
            try:
                user_input = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Designer session ended]")
                break

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "bye"):
                print("[Designer session ended]")
                break

            before = set(design_dir.glob("*.new.md"))
            await client.query(user_input)
            stop_reason, _ = await _stream_response(client, conv_log_dir, agent_name, "design")
            print()

            # If agent wrote the design doc and finished naturally, offer to exit
            if stop_reason == "end_turn" and user_input.lower() == "write":
                after = set(design_dir.glob("*.new.md"))
                for new_file in sorted(after - before):
                    append_run_log(run_log, agent_name, f"design written: {new_file.name}")
                print("\n[Design saved as .new.md — the Business Analyst will pick it up automatically.]")
                print("[Type 'exit' to close or continue refining (type 'write' again to re-queue).]")


if __name__ == "__main__":
    args = _parse_args()
    workspace_dir = resolve_path(args.workspace_dir)
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(run, workspace_dir, args.model, run_log, args.agent_name, conv_log_dir)
