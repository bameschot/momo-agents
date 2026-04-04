"""Shared agent utilities for all momo-agents."""
import json
from datetime import datetime, timezone
from pathlib import Path

import anyio

PROJECT_ROOT = Path(__file__).parent.parent
ROLES_DIR = PROJECT_ROOT / "roles"
CLAUDE_ROLES_DIR = ROLES_DIR / "claude_roles"
OLLAMA_ROLES_DIR = ROLES_DIR / "ollama_roles"


def load_role(role_name: str) -> str:
    """Read and return the system prompt for the given role file (without .md extension).

    role_name may include a subdirectory, e.g. 'claude_roles/claude_designer'
    or 'ollama_roles/ollama-business-analyst'.
    """
    return (ROLES_DIR / f"{role_name}.md").read_text()


def resolve_path(raw: str | Path) -> Path:
    """Return an absolute Path, resolving relative paths against PROJECT_ROOT."""
    p = Path(raw)
    return p if p.is_absolute() else PROJECT_ROOT / p


def append_run_log(run_log_path: Path | None, agent_name: str, message: str) -> None:
    """Append a timestamped entry to the run-log.jsonl file (one JSON object per line)."""
    if run_log_path is None:
        return
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_name": agent_name,
        "message": message,
    }
    try:
        run_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(run_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


async def wait_for_workspace(workspace_dir: Path, agent_name: str, poll_interval: int) -> None:
    """Block until workspace_dir/CLAUDE.md exists (scaffolding agent has finished)."""
    claude_md = workspace_dir / "CLAUDE.md"
    if claude_md.exists():
        return
    print(f"[{agent_name}] Waiting for scaffolding to complete ({claude_md}) — polling every {poll_interval}s...")
    while not claude_md.exists():
        await anyio.sleep(poll_interval)
    print(f"[{agent_name}] Workspace ready — proceeding.")
