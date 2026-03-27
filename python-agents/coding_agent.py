"""Coding Agent — Python orchestrates story selection; Claude implements one story."""
import re
import subprocess
import anyio
from pathlib import Path
from datetime import datetime, timezone

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

PROJECT_ROOT = Path(__file__).parent.parent
STORIES_DIR  = PROJECT_ROOT / "stories"
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
ROLES_DIR    = PROJECT_ROOT / "roles"
SENTINEL_DIR = PROJECT_ROOT / ".sentinels"

HALT_FILE         = STORIES_DIR / "HALT"
PIPELINE_COMPLETE = SENTINEL_DIR / "pipeline_complete"

POLL_INTERVAL = 10   # seconds between polls when nothing is claimable
MAX_ATTEMPTS  = 5


# ─────────────────────────────────────────────────────────────────────────────
# Story filesystem helpers — all state transitions live here, not in the LLM
# ─────────────────────────────────────────────────────────────────────────────

def _pending_stories() -> list[Path]:
    """Return bare STORY-NNN.md files only."""
    return [
        p for p in STORIES_DIR.glob("STORY-*.md")
        if re.fullmatch(r"STORY-\d+\.md", p.name)
    ]


def _read_field(path: Path, field: str) -> str:
    """Extract **Field**: value from a story header (returns '' if absent)."""
    m = re.search(rf"^\*\*{re.escape(field)}\*\*:\s*(.+)$", path.read_text(), re.MULTILINE)
    return m.group(1).strip() if m else ""


def _story_index(path: Path) -> int:
    try:
        return int(_read_field(path, "Index"))
    except ValueError:
        return 9999


def _dependency_satisfied(path: Path) -> bool:
    """
    Return True when **Depends on** is 'none'/empty, OR when the named
    dependency story already exists as a .done.md file on disk.
    Pure filesystem check — no LLM involved.
    """
    dep = _read_field(path, "Depends on").strip()
    if not dep or dep.lower() == "none":
        return True

    # Normalise: strip any suffix the BA may have written (e.g. "STORY-001.md")
    base = re.sub(r"\.(md|working\.md|done\.md|failed\.md|reviewing\.md)$", "", dep, flags=re.IGNORECASE)
    base = base.upper()
    return (STORIES_DIR / f"{base}.done.md").exists()


def _try_claim(pending: Path) -> Path | None:
    """
    Atomic rename STORY-NNN.md → STORY-NNN.working.md.
    Returns the .working.md path on success, None if another agent won the race.
    """
    stem = re.sub(r"\.md$", "", pending.name)
    working = STORIES_DIR / f"{stem}.working.md"
    try:
        pending.rename(working)
        return working
    except (FileNotFoundError, OSError):
        return None


def _increment_attempts(working: Path) -> int:
    """Increment **Attempts** in the story file; return the new value."""
    text = working.read_text()
    m = re.search(r"^(\*\*Attempts\*\*:\s*)(\d+)$", text, re.MULTILINE)
    if m:
        new_val = int(m.group(2)) + 1
        text = text[: m.start()] + f"{m.group(1)}{new_val}" + text[m.end() :]
    else:
        new_val = 1
    working.write_text(text)
    return new_val


def _release_to_pending(working: Path) -> None:
    """Rename .working.md → .md (release without failure)."""
    stem = re.sub(r"\.working\.md$", "", working.name)
    try:
        working.rename(STORIES_DIR / f"{stem}.md")
    except OSError:
        pass


def _mark_done(working: Path) -> Path:
    """Rename .working.md → .done.md and return the new path."""
    stem = re.sub(r"\.working\.md$", "", working.name)
    done = STORIES_DIR / f"{stem}.done.md"
    working.rename(done)
    return done


def _mark_failed(working: Path) -> None:
    """Rename .working.md → .failed.md and create stories/HALT."""
    stem = re.sub(r"\.working\.md$", "", working.name)
    working.rename(STORIES_DIR / f"{stem}.failed.md")
    HALT_FILE.touch()


def _halt_procedure(owned: Path | None) -> None:
    """Discard uncommitted workspace changes and release any owned story."""
    subprocess.run(
        ["git", "checkout", "--", str(WORKSPACE_DIR)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
    )
    if owned and owned.exists():
        _release_to_pending(owned)


def _find_and_claim() -> Path | None:
    """
    Sort pending stories by Index, skip those with unsatisfied dependencies,
    and atomically claim the first eligible one.
    Returns the .working.md path or None if nothing is claimable right now.
    """
    candidates = sorted(_pending_stories(), key=_story_index)
    for candidate in candidates:
        if not _dependency_satisfied(candidate):
            continue
        working = _try_claim(candidate)
        if working:
            return working
    return None


# ─────────────────────────────────────────────────────────────────────────────
# LLM implementation step — agent only sees the pre-claimed story
# ─────────────────────────────────────────────────────────────────────────────

def _result_file(working: Path) -> Path:
    stem = re.sub(r"\.working\.md$", "", working.name)
    return SENTINEL_DIR / f"{stem}.result"


async def _implement(working: Path, attempt: int) -> bool:
    """
    Call the Claude agent to implement the story already claimed at `working`.
    Returns True on success, False on failure.
    The agent signals its outcome by writing SUCCESS or FAILURE to a result file.
    """
    result_path = _result_file(working)
    result_path.unlink(missing_ok=True)  # ensure clean slate

    task = (
        f"Project root:      {PROJECT_ROOT}\n"
        f"Workspace:         {WORKSPACE_DIR}\n"
        f"Story file:        {working}\n"
        f"Attempt:           {attempt} of {MAX_ATTEMPTS}\n"
        f"Result file:       {result_path}\n\n"
        "Steps:\n"
        f"1. Read {WORKSPACE_DIR}/CLAUDE.md for build, test, and lint commands.\n"
        f"2. Read the story at {working} — understand acceptance criteria fully.\n"
        "3. Implement the acceptance criteria inside workspace/ only.\n"
        "4. Run tests and linter as instructed in CLAUDE.md.\n"
        "5a. If all tests pass and linter is clean:\n"
        f"    - Commit all workspace changes (message must reference the story ID).\n"
        f"    - Write exactly the word SUCCESS to {result_path}.\n"
        "5b. If the implementation cannot be completed or tests/linter fail:\n"
        f"    - Append a failure note below the --- separator in {working}:\n"
        f"      <!-- Attempt {attempt} — {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} -->\n"
        "      **What was tried**: <brief summary>\n"
        "      **What went wrong**: <root cause>\n"
        f"    - Write exactly the word FAILURE to {result_path}.\n"
        "Do NOT rename, move, or delete the story file. Do NOT touch stories/HALT.\n"
        "Do NOT claim or read any other story file.\n"
        "Only modify files inside workspace/."
    )

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        system_prompt=(ROLES_DIR / "coding-agent.md").read_text(),
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="acceptEdits",
        max_turns=500,
    )

    async for message in query(prompt=task, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            print(f"\n\n[Coding Agent — stop reason: {message.stop_reason}]")

    # Read result written by the agent
    try:
        result = result_path.read_text().strip().upper()
        result_path.unlink(missing_ok=True)
        return result == "SUCCESS"
    except FileNotFoundError:
        # Agent did not write a result file — treat as failure
        print("[Coding Agent] WARNING: agent did not write a result file — treating as failure.")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Main polling loop
# ─────────────────────────────────────────────────────────────────────────────

async def _wait_for_pi() -> None:
    """Block until the Project Initialiser has finished (or been skipped)."""
    pi_done = SENTINEL_DIR / "pi.done"
    if pi_done.exists():
        return
    print("[Coding Agent] Waiting for Project Initialiser to complete...")
    while not pi_done.exists():
        if PIPELINE_COMPLETE.exists():
            return
        await anyio.sleep(3)
    print("[Coding Agent] Project Initialiser ready.")


async def run() -> None:
    print(f"[Coding Agent] Started. Polling {STORIES_DIR} for eligible stories...")

    await _wait_for_pi()

    owned: Path | None = None

    while True:
        # ── Exit condition ───────────────────────────────────────────────────
        if PIPELINE_COMPLETE.exists():
            print("[Coding Agent] pipeline_complete sentinel detected — exiting.")
            break

        # ── HALT handling ────────────────────────────────────────────────────
        if HALT_FILE.exists():
            print("[Coding Agent] HALT detected — pausing until Story Reviewer clears it...")
            while HALT_FILE.exists():
                if PIPELINE_COMPLETE.exists():
                    print("[Coding Agent] pipeline_complete during HALT wait — exiting.")
                    return
                await anyio.sleep(5)
            print("[Coding Agent] HALT cleared — resuming.")
            continue

        # ── Find and claim an eligible story ─────────────────────────────────
        owned = _find_and_claim()

        if owned is None:
            print(
                f"[Coding Agent] No eligible story available — "
                f"polling again in {POLL_INTERVAL}s..."
            )
            await anyio.sleep(POLL_INTERVAL)
            continue

        story_id = re.sub(r"\.working\.md$", "", owned.name)
        attempt  = _increment_attempts(owned)
        print(f"\n[Coding Agent] Claimed {story_id} (attempt {attempt}/{MAX_ATTEMPTS})")

        # ── Pre-implementation HALT check ────────────────────────────────────
        if HALT_FILE.exists():
            print("[Coding Agent] HALT detected after claiming — releasing story.")
            _halt_procedure(owned)
            owned = None
            continue

        # ── Delegate implementation to the LLM ───────────────────────────────
        success = await _implement(owned, attempt)

        # ── Post-implementation HALT check ───────────────────────────────────
        if HALT_FILE.exists():
            print("[Coding Agent] HALT detected after implementation — performing halt procedure.")
            _halt_procedure(owned)
            owned = None
            continue

        # ── State transition based on result ─────────────────────────────────
        if success:
            if owned.exists():   # agent may have renamed it on commit — double-check
                _mark_done(owned)
            print(f"[Coding Agent] {story_id} → done ✓")
        else:
            if attempt >= MAX_ATTEMPTS:
                print(f"[Coding Agent] {story_id} exhausted {MAX_ATTEMPTS} attempts — marking failed, halting.")
                if owned.exists():
                    _mark_failed(owned)
                _halt_procedure(None)
            else:
                print(f"[Coding Agent] {story_id} failed (attempt {attempt}) — releasing to pending.")
                if owned.exists():
                    _release_to_pending(owned)

        owned = None


if __name__ == "__main__":
    anyio.run(run)
