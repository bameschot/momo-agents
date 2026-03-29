"""Shared token-usage logging utility for all momo-agents."""
import json
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

# Flush interval in seconds — accumulated tokens are written at most this often.
_FLUSH_INTERVAL = 15.0

# Per-agent accumulator: agent -> {"last_flush": float, "input": int, "output": int,
#                                   "cache_read": int, "cache_write": int}
_accumulators: dict[str, dict] = {}


def log_usage(log_file: Path | None, agent: str, usage: dict | None) -> None:
    """Accumulate token counts from *usage* and flush to *log_file* at most every
    30 seconds.  The final flush is guaranteed when the process exits via
    :func:`flush_all`.

    Safe to call with ``usage=None`` (no-op) so callers need no guard logic.
    The file and its parent directory are created automatically on first flush.
    """
    if log_file is None or not usage:
        return

    now = monotonic()
    acc = _accumulators.setdefault(
        agent,
        {"last_flush": now, "input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
         "log_file": log_file},
    )

    acc["input"] += usage.get("input_tokens", 0)
    acc["output"] += usage.get("output_tokens", 0)
    acc["cache_read"] += usage.get("cache_read_input_tokens", 0)
    acc["cache_write"] += usage.get("cache_creation_input_tokens", 0)

    if now - acc["last_flush"] >= _FLUSH_INTERVAL:
        _flush(agent, acc)


def flush_all() -> None:
    """Write any remaining accumulated tokens for all agents.  Call once on exit."""
    for agent, acc in _accumulators.items():
        if acc["input"] or acc["output"] or acc["cache_read"] or acc["cache_write"]:
            _flush(agent, acc)


def _flush(agent: str, acc: dict) -> None:
    """Write one JSONL record for *agent* and reset the accumulator."""
    log_file: Path = acc["log_file"]
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent": agent,
        "input_tokens": acc["input"],
        "output_tokens": acc["output"],
        "cache_read_tokens": acc["cache_read"],
        "cache_write_tokens": acc["cache_write"],
    }
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")

    acc["input"] = 0
    acc["output"] = 0
    acc["cache_read"] = 0
    acc["cache_write"] = 0
    acc["last_flush"] = monotonic()
