# Coding Team Architecture

**Version**: 1.0
**Date**: 2026-03-26
**Status**: Draft

---

## 1. Overview

This document describes the architecture of a multi-agent coding team built on top of the Claude Code CLI. The system decomposes a user's natural-language requirements into a designed spec, then into discrete stories, and finally into implemented code — all driven by specialised agents that coordinate through shared file system state.

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
│  Business Analyst    │  ← reads design → stories/*.md
│  Agent               │
└──────────┬───────────┘
           │
    ┌──────┴───────┐
    │              │
    ▼              ▼
┌────────┐    ┌────────┐   …  N coding agents running in parallel
│Coding  │    │Coding  │
│Agent 1 │    │Agent 2 │
└────┬───┘    └────┬───┘
     │              │
     └──────┬───────┘
            ▼
     workspace/   ← all generated code lives here
```

---

## 2. Directory Layout

```
momo-agents/                  ← orchestration repo (this repo)
├── CLAUDE.md
├── design/                   ← Designer Agent outputs
│   └── <feature-name>.md
├── stories/                  ← BA Agent outputs; claimed by Coding Agents
│   ├── STORY-001.md          ← available (unclaimed)
│   ├── STORY-002.working.md  ← claimed, in progress
│   └── STORY-003.done.md     ← completed
├── agents/                   ← agent prompt/configuration files
│   ├── designer.md
│   ├── business-analyst.md
│   └── coding-agent.md
└── workspace/                ← generated source code (treated as its own project)
    ├── src/
    ├── tests/
    └── …
```

> `workspace/` can alternatively be a **separate git repository** checked out inside this directory (see §8).

---

## 3. Agents

### 3.1 Designer Agent

**Role**: Translate raw user requirements into a structured design document.

**Invocation**:
```bash
claude -p "$(cat agents/designer.md)" --output design/<feature-name>.md
```

**Responsibilities**:
- Ask clarifying questions if requirements are ambiguous.
- Produce a design document conforming to the template in §5.1.
- Write the output to `design/<feature-name>.md`.
- Do **not** write any code or stories.

**Trigger**: Manually by the user when starting a new feature.

---

### 3.2 Business Analyst Agent

**Role**: Decompose a design document into independent, actionable stories.

**Invocation**:
```bash
claude -p "$(cat agents/business-analyst.md)" \
       --context design/<feature-name>.md
```

**Responsibilities**:
- Read the design document passed as context.
- Identify logical units of work that can be implemented independently.
- Write one story file per unit following the template in §5.2.
- Name each file `STORY-<NNN>.md` (zero-padded, sequentially assigned, e.g. `STORY-001.md`) inside `stories/`.
- Order stories so that stories with no dependencies come first.
- Do **not** write any code.

**Trigger**: Automatically after the Designer Agent completes, or manually.

---

### 3.3 Coding Agent

**Role**: Claim a single pending story and implement it in `workspace/`.

**Invocation** (run N copies in parallel):
```bash
claude -p "$(cat agents/coding-agent.md)"
```

**Responsibilities**:
- Scan `stories/` for files matching `STORY-*.md` (pending state).
- **Atomically claim** one story by renaming it from `STORY-NNN.md` → `STORY-NNN.working.md` (see §6).
- Read the story, implement the required changes inside `workspace/`.
- Run any tests/linters defined in the story or in `workspace/CLAUDE.md`.
- On success: rename `STORY-NNN.working.md` → `STORY-NNN.done.md`.
- On failure: rename `STORY-NNN.working.md` → `STORY-NNN.failed.md` and append a failure summary at the bottom of the story file.
- Exit when no more pending stories exist.

**Trigger**: Spawned by the orchestrator (see §7) after the BA Agent writes stories.

---

## 4. Story Lifecycle

```
           ┌──────────────────────────────────────────┐
           │             stories/ directory            │
           │                                           │
  written  │  STORY-NNN.md                            │
  ─────────►  (pending — any agent may claim)         │
           │          │                               │
   atomic  │          │ rename (claim)                │
   rename  │          ▼                               │
           │  STORY-NNN.working.md                    │
           │  (owned by exactly one Coding Agent)     │
           │          │                               │
           │     ┌────┴────┐                          │
           │  success    failure                      │
           │     │           │                        │
           │     ▼           ▼                        │
           │  STORY-NNN   STORY-NNN                   │
           │  .done.md    .failed.md                  │
           └──────────────────────────────────────────┘
```

| Filename pattern           | State      | Claimable |
|----------------------------|------------|-----------|
| `STORY-NNN.md`             | Pending    | Yes       |
| `STORY-NNN.working.md`     | In progress| No        |
| `STORY-NNN.done.md`        | Complete   | No        |
| `STORY-NNN.failed.md`      | Failed     | Manual retry only |

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

**Design ref**: design/<feature-name>.md
**Depends on**: STORY-NNN (or "none")
**Complexity**: S | M | L

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
<!-- Coding Agent appends below this line -->
```

---

## 6. Atomic Story Claiming

Because multiple Coding Agents run in parallel they must not work on the same story. The coordination mechanism is an **atomic file rename**, which the OS guarantees on a single filesystem (POSIX `rename(2)` is atomic; Windows `MoveFileEx` with `MOVEFILE_REPLACE_EXISTING` provides equivalent semantics).

### Claiming algorithm (Python pseudocode)

```python
import os
import glob

def claim_story(stories_dir: str) -> str | None:
    """
    Attempt to atomically claim a pending story.
    Returns the .working path on success, None if no stories remain.
    """
    for pending in sorted(glob.glob(f"{stories_dir}/STORY-*.md")):
        # Exclude already-claimed/done/failed files
        base = os.path.basename(pending)
        if "." in base[len("STORY-XXX"):]:   # has a second extension
            continue

        working = pending.replace(".md", ".working.md")
        try:
            os.rename(pending, working)   # atomic on POSIX
            return working
        except FileNotFoundError:
            # Another agent claimed it first — try the next one
            continue
    return None
```

The rename either succeeds (the agent now owns the story) or raises `FileNotFoundError` (another agent won the race). No locks, no database — just the filesystem.

---

## 7. Orchestrator

A lightweight shell script (or Python script) coordinates the full pipeline:

```bash
#!/usr/bin/env bash
# orchestrate.sh  — run the full pipeline for a given requirements file

set -euo pipefail

REQUIREMENTS=$1          # path to a plain-text requirements file
FEATURE_NAME=$2          # slug used for filenames, e.g. "user-auth"
N_CODERS=${3:-3}         # number of parallel Coding Agents

# ── Step 1: Design ──────────────────────────────────────────────────
echo "[1/3] Running Designer Agent…"
claude -p "$(cat agents/designer.md)

## User Requirements
$(cat "$REQUIREMENTS")" \
  > "design/${FEATURE_NAME}.md"

# ── Step 2: Break into stories ───────────────────────────────────────
echo "[2/3] Running Business Analyst Agent…"
claude -p "$(cat agents/business-analyst.md)

## Design Document
$(cat "design/${FEATURE_NAME}.md")"

# ── Step 3: Parallel coding ──────────────────────────────────────────
echo "[3/3] Spawning ${N_CODERS} Coding Agent(s)…"
for i in $(seq 1 "$N_CODERS"); do
  claude -p "$(cat agents/coding-agent.md)" &
done
wait

echo "Done. Check stories/ for status and workspace/ for code."
```

> **Note**: For long-running or heavily parallelised workloads, consider using `tmux`, `parallel`, or a proper process supervisor instead of bare `&`.

---

## 8. Workspace Repository

The `workspace/` directory contains the project being built. It should have its own `CLAUDE.md` describing its conventions so Coding Agents know how to build, test, and lint the project.

```
workspace/
├── CLAUDE.md          ← project-specific instructions for Coding Agents
├── pyproject.toml     ← (or package.json, Cargo.toml, etc.)
├── src/
└── tests/
```

`workspace/` may be:
- A subdirectory tracked within the same git repo.
- A **separate git repository** cloned here (`git clone <target-repo> workspace/`). Add `workspace/` to `.gitignore` in this case to keep the repos independent.

---

## 9. Agent Prompt Files

Each agent reads its system prompt from a file in `agents/`. These files describe the agent's role, tools it may use, and hard constraints. They are plain Markdown passed via `claude -p`.

| File                        | Purpose                              |
|-----------------------------|--------------------------------------|
| `agents/designer.md`        | System prompt for the Designer Agent |
| `agents/business-analyst.md`| System prompt for the BA Agent       |
| `agents/coding-agent.md`    | System prompt for Coding Agents      |

---

## 10. Constraints and Guardrails

| Constraint | Where enforced |
|---|---|
| One agent per story | Atomic rename (§6) |
| No direct writes to `design/` or `stories/` by Coding Agents | Agent system prompt |
| No writes outside `workspace/` by Coding Agents | Agent system prompt |
| Designer Agent does not write stories or code | Agent system prompt |
| BA Agent does not write code | Agent system prompt |
| Secrets never committed | `.gitignore` excludes `.env` |

---

## 11. Open Questions

1. **Retry policy** — should failed stories be automatically retried, and how many times?
2. **Story dependencies** — should Coding Agents block on dependent stories being done before starting?
3. **Workspace repo** — same repo vs. separate repo; needs a decision before implementation.
4. **Designer interaction** — should the Designer Agent be interactive (ask clarifying questions mid-session) or produce a draft in a single pass?
5. **Observability** — a `status.sh` script that prints a summary of story states would be useful.
