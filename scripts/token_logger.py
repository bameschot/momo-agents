"""Shared token-usage logging utility for all momo-agents."""
import json
from datetime import datetime, timezone
from pathlib import Path


def log_usage(log_file: Path | None, agent: str, usage: dict | None) -> None:
    """Append one JSONL record to *log_file* with token counts from *usage*.

    Safe to call with ``usage=None`` (no-op) so callers need no guard logic.
    The file and its parent directory are created automatically.
    """
    if log_file is None or not usage:
        return

    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent": agent,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
        "cache_write_tokens": usage.get("cache_creation_input_tokens", 0),
    }
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")
