"""Shared agent utilities for all momo-agents."""
from pathlib import Path

import anyio

PROJECT_ROOT = Path(__file__).parent.parent
ROLES_DIR = PROJECT_ROOT / "roles"


def load_role(role_name: str) -> str:
    """Read and return the system prompt for the given role file (without .md extension)."""
    return (ROLES_DIR / f"{role_name}.md").read_text()


def resolve_path(raw: str | Path) -> Path:
    """Return an absolute Path, resolving relative paths against PROJECT_ROOT."""
    p = Path(raw)
    return p if p.is_absolute() else PROJECT_ROOT / p


async def wait_for_workspace(workspace_dir: Path, agent_name: str, poll_interval: int) -> None:
    """Block until workspace_dir/CLAUDE.md exists (scaffolding agent has finished)."""
    claude_md = workspace_dir / "CLAUDE.md"
    if claude_md.exists():
        return
    print(f"[{agent_name}] Waiting for scaffolding to complete ({claude_md}) — polling every {poll_interval}s...")
    while not claude_md.exists():
        await anyio.sleep(poll_interval)
    print(f"[{agent_name}] Workspace ready — proceeding.")
