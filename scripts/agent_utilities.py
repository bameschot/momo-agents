"""Shared agent utilities for all momo-agents."""
from pathlib import Path

import anyio


async def wait_for_workspace(workspace_dir: Path, agent_name: str, poll_interval: int) -> None:
    """Block until workspace_dir/CLAUDE.md exists (scaffolding agent has finished)."""
    claude_md = workspace_dir / "CLAUDE.md"
    if claude_md.exists():
        return
    print(f"[{agent_name}] Waiting for scaffolding to complete ({claude_md}) — polling every {poll_interval}s...")
    while not claude_md.exists():
        await anyio.sleep(poll_interval)
    print(f"[{agent_name}] Workspace ready — proceeding.")
