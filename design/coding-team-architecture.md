# Coding Team Architecture

**Version**: 1.2
**Date**: 2026-03-26
**Status**: Draft

---

## 1. Overview

This document describes the architecture of a multi-agent coding team built on top of the Claude Code CLI. The system decomposes a user's natural-language requirements into a designed spec, then into discrete ordered stories, and finally into implemented code — all driven by specialised agents that coordinate through shared file system state.

```
User ◄──────────────────────────────────────────────────────────────┐
 │                                                                   │ provides guidance
 ▼                                                                   │
┌─────────────────┐                                       ┌──────────────────┐
│  Designer Agent │  ← interprets requirements            │  Story Reviewer  │
│                 │    → design/*.md                      │  Agent           │
└────────┬────────┘                                       └──────────────────┘
         │                                                          ▲
         ▼                                                          │ claims .failed.md
┌──────────────────────┐                                           │
│  Business Analyst    │  ← reads design → stories/*.md           │
│  Agent               │     (with index + attempts counter)       │
└──────────┬───────────┘                                           │
           │                                           ┌───────────┘
    ┌──────┴───────┐                          after 5 failures
    │              │
    ▼              ▼
┌────────┐    ┌────────┐   …  N coding agents running in parallel
│Coding  │    │Coding  │       each picks the lowest-index pending story
│Agent 1 │    │Agent 2 │
└────┬───┘    └────┬───┘
     │              │
     └──────┬───────┘
            ▼
     workspace/   ← all generated code lives here (same repo)
```

---

## 2. Directory Layout

```
momo-agents/                  ← this repo
├── CLAUDE.md
├── design/                   ← Designer Agent outputs
│   └── <feature-name>.md
├── stories/                  ← BA Agent outputs; claimed by Coding Agents
│   ├── STORY-001.md          ← pending (index 1 — highest priority)
│   ├── STORY-002.working.md  ← claimed, in progress
│   ├── STORY-003.done.md     ← completed
│   └── STORY-004.failed.md   ← exhausted retries; awaiting Story Reviewer
├── roles/                    ← system prompt files read by each agent
│   ├── designer.md
│   ├── business-analyst.md
│   ├── coding-agent.md
│   └── story-reviewer.md
└── workspace/                ← generated source code (same repo, committed here)
    ├── CLAUDE.md             ← workspace-specific conventions for Coding Agents
    ├── src/
    └── tests/
```

---

## 3. Agents

### 3.1 Designer Agent

**Role**: Translate raw user requirements into a structured design document.

**System prompt**: `roles/designer.md`

**Invocation**:
```bash
claude -p "$(cat roles/designer.md)

## User Requirements
$(cat requirements.md)" \
  > "design/${FEATURE_NAME}.md"
```

**Responsibilities**:
- Ask clarifying questions if requirements are ambiguous (interactive mode).
- Produce a design document conforming to the template in §5.1.
- Write the output to `design/<feature-name>.md`.
- Do **not** write stories or code.

**Trigger**: Manually by the user when starting a new feature.

---

### 3.2 Business Analyst Agent

**Role**: Decompose a design document into independent, ordered, actionable stories.

**System prompt**: `roles/business-analyst.md`

**Invocation**:
```bash
claude -p "$(cat roles/business-analyst.md)

## Design Document
$(cat "design/${FEATURE_NAME}.md")"
```

**Responsibilities**:
- Read the design document passed as context.
- Identify logical units of work that can be implemented independently.
- Assign each story a sequential **index** starting at 1; record it inside the story file as `**Index**: N`.
- Order stories so that foundational work (no dependencies) has lower index numbers.
- Initialise `**Attempts**: 0` in every story file.
- Write one story file per unit to `stories/STORY-<NNN>.md` following the template in §5.2.
- Do **not** write code.

**Trigger**: After the Designer Agent completes, or manually.

---

### 3.3 Coding Agent

**Role**: Claim the lowest-index pending story, implement it in `workspace/`, and manage the retry counter.

**System prompt**: `roles/coding-agent.md`

**Invocation** (run N copies in parallel):
```bash
claude -p "$(cat roles/coding-agent.md)"
```

**Responsibilities**:
1. Scan `stories/` for all files matching `STORY-*.md` (pending — no secondary extension).
2. Parse the `**Index**` field from each pending story file.
3. Sort by index ascending and **atomically claim** the lowest by renaming `STORY-NNN.md` → `STORY-NNN.working.md` (see §6).
4. If the rename fails (another agent claimed it first), move to the next lowest and retry.
5. Increment `**Attempts**` in the story file.
6. Read `workspace/CLAUDE.md` for project context, then implement the story requirements.
7. Run all tests and linters defined in the story or in `workspace/CLAUDE.md`.
8. On **success**: rename `STORY-NNN.working.md` → `STORY-NNN.done.md`.
9. On **failure**:
   - Append a timestamped failure note to the story file (see §6).
   - If `**Attempts**` has now reached **5**: rename `STORY-NNN.working.md` → `STORY-NNN.failed.md` (terminal — Story Reviewer takes over).
   - Otherwise: rename `STORY-NNN.working.md` → `STORY-NNN.md` (returns to pending queue).
10. Loop back to step 1. Exit only when no pending stories remain.

**Trigger**: Spawned by the orchestrator (see §7) after the BA Agent writes stories.

---

### 3.4 Story Reviewer Agent

**Role**: Triage permanently-failed stories, summarise what was attempted, and rewrite the story with user guidance before returning it to the queue.

**System prompt**: `roles/story-reviewer.md`

**Invocation**:
```bash
claude "$(cat roles/story-reviewer.md)"   # interactive — must have terminal access
```

**Responsibilities**:
1. Scan `stories/` for files matching `STORY-*.failed.md`.
2. **Atomically claim** a failed story by renaming `STORY-NNN.failed.md` → `STORY-NNN.reviewing.md`.
3. Read the full story file, including all appended failure notes.
4. Present to the user:
   - The original story goal and acceptance criteria.
   - A concise summary of each failed attempt and what went wrong.
5. **Wait for user input**: ask the user how the story should be rewritten — a new approach, relaxed constraints, split into smaller stories, or any other guidance.
6. Rewrite the story file **in full** using the user's guidance: replace all content with a clean story conforming to the §5.2 template, reset `**Attempts**: 0`, and preserve the `**Index**` value.
7. Atomically rename `STORY-NNN.reviewing.md` → `STORY-NNN.md` (returns to pending queue for Coding Agents).
8. Continue to the next `.failed.md` file, or exit if none remain.

**Trigger**: Manually by the user when failed stories are present, or run continuously alongside Coding Agents.

---

## 4. Story Lifecycle

```
           ┌────────────────────────────────────────────────────────────┐
           │                    stories/ directory                       │
           │                                                             │
  written  │  STORY-NNN.md  (Index: N, Attempts: 0)                    │
  ─────────►  (pending — any Coding Agent may claim)                    │
           │          │                                                  │
   atomic  │          │ rename (claim)                                   │
   rename  │          ▼                                                  │
           │  STORY-NNN.working.md                                       │
           │  (owned by exactly one Coding Agent; Attempts incremented) │
           │          │                                                  │
           │     ┌────┴──────┐                                          │
           │  success      failure                                       │
           │     │              │                                        │
           │     ▼              ▼ append failure note                    │
           │  STORY-NNN     attempts < 5?                               │
           │  .done.md      ├─ yes → rename back to STORY-NNN.md        │
           │                │         (pending again)                    │
           │                └─ no  → rename to STORY-NNN.failed.md      │
           │                                    │                        │
           │                          ┌─────────┘                       │
           │               atomic     │ rename (claim)                  │
           │               rename     ▼                                  │
           │                  STORY-NNN.reviewing.md                    │
           │                  (owned by Story Reviewer Agent)           │
           │                          │                                  │
           │                   user provides guidance                    │
           │                   story rewritten in full                   │
           │                   Attempts reset to 0                       │
           │                          │                                  │
           │                          ▼ rename                           │
           │                  STORY-NNN.md (pending again)              │
           └────────────────────────────────────────────────────────────┘
```

| Filename pattern           | State      | Claimable by         |
|----------------------------|------------|----------------------|
| `STORY-NNN.md`             | Pending    | Any Coding Agent     |
| `STORY-NNN.working.md`     | In progress| — (owned)            |
| `STORY-NNN.done.md`        | Complete   | Nobody               |
| `STORY-NNN.failed.md`      | Exhausted  | Story Reviewer Agent |
| `STORY-NNN.reviewing.md`   | Under review| — (owned)           |

---

## 5. File Templates

### 5.1 Design Document (`design/<feature-name>.md`)

```markdown
# Design: <Feature Name>

**Date**: YYYY-MM-DD
**Author**: Designer Agent
**Status**: Draft | Approved

## Summary
One-paragraph description of the feature.

## Goals
- Goal 1
- Goal 2

## Non-Goals
- What is explicitly out of scope.

## Architecture
High-level description with diagrams (Mermaid or ASCII).

## Data Model
Key entities, schemas, or data structures.

## API / Interface
Public surface (functions, endpoints, CLI flags, etc.).

## Error Handling
Known failure modes and how they are addressed.

## Open Questions
Any unresolved decisions the BA or coder should be aware of.
```

---

### 5.2 Story File (`stories/STORY-NNN.md`)

```markdown
# STORY-NNN: <Short Title>

**Index**: N
**Attempts**: 0
**Design ref**: design/<feature-name>.md
**Depends on**: STORY-NNN | none

## Context
Why this story exists; what problem it solves.

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Implementation Hints
Optional notes on approach, file locations, or APIs to use.

## Test Requirements
Describe the tests that must pass for this story to be considered done.

---
<!-- Coding Agent appends attempt notes below this line -->
```

Both the `**Index**` and `**Attempts**` fields are machine-readable and must appear verbatim in the header. When the Story Reviewer rewrites a story it replaces **all content** above and below the separator but preserves the original `**Index**` value and resets `**Attempts**` to `0`.

---

## 6. Atomic Story Claiming and Retry Logic

Multiple agents run in parallel and must not work on the same story. The coordination mechanism is an **atomic file rename** — POSIX `rename(2)` is guaranteed atomic on a single filesystem, so exactly one agent wins when multiple agents race for the same file.

### Coding Agent: claim and execute (Python pseudocode)

```python
import os
import re
import glob
from datetime import datetime, timezone

MAX_ATTEMPTS = 5

def read_field(path: str, field: str) -> int:
    """Extract **Field**: N from a story file. Returns 0 if missing."""
    pattern = re.compile(rf"\*\*{re.escape(field)}\*\*:\s*(\d+)")
    with open(path) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                return int(m.group(1))
    return 0

def set_field(path: str, field: str, value: int) -> None:
    """Update **Field**: N in-place inside a story file."""
    pattern = re.compile(rf"(\*\*{re.escape(field)}\*\*:\s*)(\d+)")
    with open(path) as f:
        content = f.read()
    content = pattern.sub(lambda m: f"{m.group(1)}{value}", content, count=1)
    with open(path, "w") as f:
        f.write(content)

def claim_next_story(stories_dir: str) -> str | None:
    """
    Find the lowest-index pending story and atomically claim it.
    Returns the .working path on success, None if no stories remain.
    """
    while True:
        pending = [
            p for p in glob.glob(f"{stories_dir}/STORY-*.md")
            if not any(p.endswith(ext) for ext in
                       (".working.md", ".done.md", ".failed.md", ".reviewing.md"))
        ]
        if not pending:
            return None

        pending.sort(key=lambda p: (read_field(p, "Index"), p))

        claimed_any = False
        for story_path in pending:
            working_path = story_path[:-3] + ".working.md"
            try:
                os.rename(story_path, working_path)   # atomic on POSIX
                claimed_any = True
                return working_path
            except FileNotFoundError:
                continue   # another agent won the race — try next

        if not claimed_any:
            return None   # all candidates vanished; no stories left

def attempt_story(working_path: str) -> bool:
    """Increment attempts counter and implement the story. Returns True on success."""
    attempts = read_field(working_path, "Attempts") + 1
    set_field(working_path, "Attempts", attempts)
    # … implementation, tests, linting …
    success = run_implementation(working_path)
    return success

def complete_story(working_path: str) -> None:
    done_path = working_path.replace(".working.md", ".done.md")
    os.rename(working_path, done_path)

def fail_story(working_path: str, failure_note: str) -> None:
    """Either release the story back to pending or mark it permanently failed."""
    attempts = read_field(working_path, "Attempts")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(working_path, "a") as f:
        f.write(f"\n### Attempt {attempts} failed — {timestamp}\n{failure_note}\n")

    if attempts >= MAX_ATTEMPTS:
        failed_path = working_path.replace(".working.md", ".failed.md")
        os.rename(working_path, failed_path)   # terminal — Story Reviewer takes over
    else:
        pending_path = working_path.replace(".working.md", ".md")
        os.rename(working_path, pending_path)   # back to pending queue
```

### Story Reviewer Agent: claim and rewrite (Python pseudocode)

```python
def claim_failed_story(stories_dir: str) -> str | None:
    """Atomically claim the next failed story for review."""
    for failed in sorted(glob.glob(f"{stories_dir}/STORY-*.failed.md")):
        reviewing_path = failed.replace(".failed.md", ".reviewing.md")
        try:
            os.rename(failed, reviewing_path)
            return reviewing_path
        except FileNotFoundError:
            continue
    return None

def review_story(reviewing_path: str, user_guidance: str) -> None:
    """
    Rewrite the story in full using user guidance, reset Attempts,
    then return it to the pending queue.
    """
    original_index = read_field(reviewing_path, "Index")

    new_content = generate_rewritten_story(
        reviewing_path,    # contains full attempt history for context
        user_guidance,
        original_index,
    )
    # Replace entire file content
    with open(reviewing_path, "w") as f:
        f.write(new_content)   # Attempts: 0 is written in new_content

    pending_path = reviewing_path.replace(".reviewing.md", ".md")
    os.rename(reviewing_path, pending_path)   # back to pending queue
```

---

## 7. Orchestrator

```bash
#!/usr/bin/env bash
# orchestrate.sh  — run the full pipeline for a feature

set -euo pipefail

REQUIREMENTS=$1          # path to a plain-text requirements file
FEATURE_NAME=$2          # slug used for filenames, e.g. "user-auth"
N_CODERS=${3:-3}         # number of parallel Coding Agents

# ── Step 1: Design ──────────────────────────────────────────────────
echo "[1/3] Running Designer Agent…"
claude -p "$(cat roles/designer.md)

## User Requirements
$(cat "$REQUIREMENTS")" \
  > "design/${FEATURE_NAME}.md"

# ── Step 2: Break into stories ───────────────────────────────────────
echo "[2/3] Running Business Analyst Agent…"
claude -p "$(cat roles/business-analyst.md)

## Design Document
$(cat "design/${FEATURE_NAME}.md")"

# ── Step 3: Parallel coding ──────────────────────────────────────────
echo "[3/3] Spawning ${N_CODERS} Coding Agent(s)…"
for i in $(seq 1 "$N_CODERS"); do
  claude -p "$(cat roles/coding-agent.md)" &
done
wait

# ── Step 4: Review any failed stories (interactive) ──────────────────
if ls stories/*.failed.md 1>/dev/null 2>&1; then
  echo "Failed stories detected. Launching Story Reviewer (interactive)…"
  claude "$(cat roles/story-reviewer.md)"
fi

echo "Done. Check stories/ for status and workspace/ for code."
```

> **Note**: Step 4 launches the Story Reviewer interactively in the foreground. For long-running pipelines you may want to run it in a separate terminal (`tmux new-window`) so Coding Agents and the Reviewer can run concurrently.

---

## 8. Workspace

`workspace/` lives inside this repository and is committed alongside the orchestration files. It must contain its own `CLAUDE.md` so that Coding Agents understand how to build, test, and lint the project.

```
workspace/
├── CLAUDE.md          ← mandatory: build/test/lint commands, conventions
├── pyproject.toml     ← (or package.json, Cargo.toml, etc.)
├── src/
└── tests/
```

Coding Agents read `workspace/CLAUDE.md` at the start of each story to understand the project context before making changes.

---

## 9. Role Files

Each agent reads its system prompt from a Markdown file in `roles/`. These files define the agent's goals, allowed actions, and hard constraints.

| File                          | Agent                  | Key constraints                                                              |
|-------------------------------|------------------------|------------------------------------------------------------------------------|
| `roles/designer.md`           | Designer Agent         | Write only to `design/`; no stories or code                                 |
| `roles/business-analyst.md`   | Business Analyst Agent | Write only to `stories/`; set Index and Attempts: 0; no code                |
| `roles/coding-agent.md`       | Coding Agent           | Claim by index order; write only to `workspace/`; manage Attempts counter    |
| `roles/story-reviewer.md`     | Story Reviewer Agent   | Claim `.failed.md` only; rewrite story with user guidance; reset Attempts    |

---

## 10. Constraints and Guardrails

| Constraint | Mechanism |
|---|---|
| One agent per story at a time | Atomic rename (§6) |
| Stories worked in priority order | `**Index**` field parsed before claiming (§6) |
| Failed stories re-enter the queue automatically | Release-by-rename when `Attempts < 5` (§6) |
| Stories failing 5 times escalate to human review | Rename to `.failed.md`; Story Reviewer waits for user input (§3.4) |
| Story Reviewer rewrites story entirely | Full content replacement; `Attempts` reset to 0 (§6) |
| Coding Agents write only to `workspace/` | `roles/coding-agent.md` system prompt |
| Designer Agent writes only to `design/` | `roles/designer.md` system prompt |
| BA Agent writes only to `stories/` | `roles/business-analyst.md` system prompt |
| Story Reviewer writes only to `stories/` | `roles/story-reviewer.md` system prompt |
| Secrets never committed | `.gitignore` excludes `.env`, `.envrc` |

---

## 11. Open Questions

1. **Story dependencies** — should a Coding Agent skip a story whose `**Depends on**` is not yet `done`, or is index ordering sufficient to handle sequencing?
2. **Designer interaction** — interactive clarification session vs. single-pass draft with open questions appended?
3. **Workspace initialisation** — who creates `workspace/CLAUDE.md` and the project scaffold before the first Coding Agent runs?
4. **Observability** — a `status.sh` script printing a summary table of story states (pending / working / done / failed / reviewing counts) would be useful for operators monitoring a run.
5. **Stale working files** — if a Coding Agent process is killed mid-story, its `.working.md` file is never released. A watchdog or manual `mv STORY-NNN.working.md STORY-NNN.md` may be needed.
6. **Concurrent review** — if multiple stories fail simultaneously, should a single Story Reviewer handle them sequentially, or can multiple Reviewer instances run in parallel (each waiting for user input)?
