"""Designer Agent — interactive multi-turn Q&A session that produces design/<feature>.new.md."""
import argparse
import anyio
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

PROJECT_ROOT = Path(__file__).parent.parent
ROLES_DIR = PROJECT_ROOT / "roles"

DEFAULT_MODEL = "claude-sonnet-4-6"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Designer Agent")
    parser.add_argument(
        "--design-dir",
        default=str(PROJECT_ROOT / "design"),
        help="Directory where design documents are written (default: <project-root>/design)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )
    return parser.parse_args()


def _system_prompt() -> str:
    return (ROLES_DIR / "designer.md").read_text()


def _initial_prompt(design_dir: Path) -> str:
    return (
        f"Project root: {PROJECT_ROOT}\n"
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


async def _stream_response(client: ClaudeSDKClient) -> str | None:
    """Stream and print the agent's response. Returns stop_reason."""
    stop_reason = None
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            stop_reason = message.stop_reason
    return stop_reason


async def run(design_dir: Path, model: str) -> None:
    design_dir.mkdir(parents=True, exist_ok=True)

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        system_prompt=_system_prompt(),
        allowed_tools=["Read", "Write"],
        permission_mode="acceptEdits",
        max_turns=50,
        model=model,
    )

    async with ClaudeSDKClient(options=options) as client:
        # Initial greeting turn
        await client.query(_initial_prompt(design_dir))
        await _stream_response(client)
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

            await client.query(user_input)
            stop_reason = await _stream_response(client)
            print()

            # If agent wrote the design doc and finished naturally, offer to exit
            if stop_reason == "end_turn" and user_input.lower() == "write":
                print("\n[Design saved as .new.md — the Business Analyst will pick it up automatically.]")
                print("[Type 'exit' to close or continue refining (type 'write' again to re-queue).]")


if __name__ == "__main__":
    args = _parse_args()
    design_dir = Path(args.design_dir)
    if not design_dir.is_absolute():
        design_dir = PROJECT_ROOT / design_dir
    anyio.run(run, design_dir, args.model)
