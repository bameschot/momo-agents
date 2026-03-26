# Coding Team Architecture

**Version**: 1.1
**Date**: 2026-03-26
**Status**: Draft

---

## 1. Overview

This document describes the architecture of a multi-agent coding team built on top of the Claude Code CLI. The system decomposes a user's natural-language requirements into a designed spec, then into discrete ordered stories, and finally into implemented code — all driven by specialised agents that coordinate through shared file system state.

```
User
 │
 ▼
┌─────────────────┐
│  Designer Agent │  ← interprets requirements → design/*.md
└────────┬────────┘
         │
         ▼
┌──────────────────────┐
│  Business Analyst    │  ← reads design → stories/*.md (with index)
│  Agent               │
└──────────┬───────────┘
           │
    ┌──────┴───────┐
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
│   └── STORY-003.done.md     ← completed
├── roles/                    ← system prompt files read by each agent
│   ├── designer.md
│   ├── business-analyst.md
│   └── coding-agent.md
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
- Write one story file per unit to `stories/STORY-<NNN>.md` following the template in §5.2.
- Do **not** write code.

**Trigger**: After the Designer Agent completes, or manually.

---

### 3.3 Coding Agent

**Role**: Claim the lowest-index pending story and implement it in `workspace/`.

**System prompt**: `roles/coding-agent.md`

**Invocation** (run N copies in parallel):
```bash
claude -p "$(cat roles/coding-agent.md)"
```

**Responsibilities**:
1. Scan `stories/` for all files matching `STORY-*.md` (pending state — no secondary extension).
2. Parse the `**Index**` field from each pending story file.
3. Sort by index ascending and **atomically claim** the lowest by renaming `STORY-NNN.md` → `STORY-NNN.working.md` (see §6).
4. If the rename fails (another agent claimed it first), move to the next lowest and retry.
5. Read the claimed story and implement the required changes in `workspace/`.
6. Run any tests and linters defined in the story or in `workspace/CLAUDE.md`.
7. On **success**: rename `STORY-NNN.working.md` → `STORY-NNN.done.md`.
8. On **failure**: rename `STORY-NNN.working.md` back to `STORY-NNN.md` so another agent can pick it up; append a brief failure note at the bottom of the story file before releasing it.
9. Loop back to step 1. Exit only when no pending stories remain.

**Trigger**: Spawned by the orchestrator (see §7) after the BA Agent writes stories.

---

## 4. Story Lifecycle

```
           ┌─────────────────────────────────────────────┐
           │              stories/ directory              │
           │                                              │
  written  │  STORY-NNN.md   (index N inside the file)  │
  ─────────►  (pending — any agent may claim)            │
           │          │                                   │
   atomic  │          │ rename (claim)                    │
   rename  │          ▼                                   │
           │  STORY-NNN.working.md                        │
           │  (owned by exactly one Coding Agent)         │
           │          │                                   │
           │     ┌────┴──────┐                            │
           │  success      failure                        │
           │     │              │                         │
           │     ▼              ▼ rename back             │
           │  STORY-NNN      STORY-NNN.md                 │
           │  .done.md       (pending again)              │
           └─────────────────────────────────────────────┘
```

| Filename pattern        | State           | Claimable |
|-------------------------|-----------------|-----------|
| `STORY-NNN.md`          | Pending         | Yes       |
| `STORY-NNN.working.md`  | In progress     | No        |
| `STORY-NNN.done.md`     | Complete        | No        |

Agents never create a permanent failure state. A story that cannot be completed is returned to pending so the next available agent can attempt it. Repeated failures will be visible as appended notes at the bottom of the story file.

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

The `**Index**` field is the primary ordering key used by Coding Agents to decide which story to claim next.

---

## 6. Atomic Story Claiming

Multiple Coding Agents run in parallel and must not work on the same story. The coordination mechanism is an **atomic file rename** — POSIX `rename(2)` is guaranteed atomic on a single filesystem, so exactly one agent wins when multiple agents try to claim the same file.

### Claiming algorithm (Python pseudocode)

```python
import os
import re
import glob

def read_index(path: str) -> int:
    """Extract **Index**: N from a story file. Returns infinity if missing."""
    with open(path) as f:
        for line in f:
            m = re.match(r"\*\*Index\*\*:\s*(\d+)", line)
            if m:
                return int(m.group(1))
    return float("inf")

def claim_next_story(stories_dir: str) -> str | None:
    """
    Find the lowest-index pending story and atomically claim it.
    Returns the .working path on success, None if no stories remain.
    """
    while True:
        # Collect all pending stories (exactly one .md extension, no second dot-segment)
        pending = [
            p for p in glob.glob(f"{stories_dir}/STORY-*.md")
            if p.endswith(".md") and not p.endswith(".working.md") and not p.endswith(".done.md")
        ]
        if not pending:
            return None

        # Sort by index field inside the file, then by filename as tiebreaker
        pending.sort(key=lambda p: (read_index(p), p))

        for story_path in pending:
            working_path = story_path[:-3] + ".working.md"   # replace .md → .working.md
            try:
                os.rename(story_path, working_path)   # atomic on POSIX
                return working_path
            except FileNotFoundError:
                # Another agent claimed this one first — try the next
                continue

        # All candidates were claimed by the time we tried; re-scan
```

On failure, the agent releases the story by renaming it back:

```python
def release_story(working_path: str, failure_note: str) -> None:
    """Return a story to pending after a failed attempt."""
    pending_path = working_path.replace(".working.md", ".md")
    with open(working_path, "a") as f:
        f.write(f"\n### Attempt failed\n{failure_note}\n")
    os.rename(working_path, pending_path)   # atomic — story is claimable again
```

---

## 7. Orchestrator

A lightweight shell script coordinates the full pipeline:

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

echo "Done. Check stories/ for status and workspace/ for code."
```

> **Note**: For heavily parallelised workloads, consider `tmux new-window` per agent so each has a visible terminal, or use GNU `parallel` for process management.

---

## 8. Workspace

`workspace/` lives inside this repository and is committed alongside the orchestration files. It must contain its own `CLAUDE.md` so that Coding Agents understand how to build, test, and lint the project without needing external instructions.

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

Each agent reads its system prompt from a Markdown file in `roles/`. These files define the agent's goals, allowed actions, and hard constraints. They are passed to the Claude Code CLI via the `-p` flag.

| File                          | Agent                  | Key constraints                                      |
|-------------------------------|------------------------|------------------------------------------------------|
| `roles/designer.md`           | Designer Agent         | Write only to `design/`; no stories or code          |
| `roles/business-analyst.md`   | Business Analyst Agent | Write only to `stories/`; assign sequential index; no code |
| `roles/coding-agent.md`       | Coding Agent           | Claim by index order; write only to `workspace/`; release on failure |

---

## 10. Constraints and Guardrails

| Constraint | Mechanism |
|---|---|
| One agent per story | Atomic rename (§6) |
| Stories worked in priority order | Index field parsed before claiming (§6) |
| Failed stories re-enter the queue | Release-by-rename rather than terminal failure state (§4) |
| Coding Agents write only to `workspace/` | `roles/coding-agent.md` system prompt |
| Designer Agent writes only to `design/` | `roles/designer.md` system prompt |
| BA Agent writes only to `stories/` | `roles/business-analyst.md` system prompt |
| Secrets never committed | `.gitignore` excludes `.env`, `.envrc` |

---

## 11. Open Questions

1. **Story dependencies** — should a Coding Agent skip a story whose dependency (`**Depends on**`) is not yet `done`, or is index ordering sufficient to handle sequencing?
2. **Designer interaction** — interactive clarification session vs. single-pass draft with open questions appended?
3. **Workspace initialisation** — who creates `workspace/CLAUDE.md` and the project scaffold before the first Coding Agent runs?
4. **Observability** — a `status.sh` script printing a summary table of story states (pending / working / done counts) would be useful for operators monitoring a run.
5. **Stale working files** — if a Coding Agent process is killed mid-story, its `.working.md` file is never released. A watchdog timeout or manual recovery process may be needed.
