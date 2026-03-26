# Momo Agents — System Design Summary

## What It Is

A multi-agent coding team built on the Claude Code CLI. The user describes what they want; a pipeline of specialised agents turns that into a design, breaks it into stories, implements the stories in parallel, and escalates to the user only when something is truly stuck.

---

## Agents and Their Roles

| Agent | Role | Reads from | Writes to |
|---|---|---|---|
| **Designer** | Interactive Q&A with user; writes design on `write` command | User input | `design/` |
| **Business Analyst** | Breaks a design into ordered, discrete stories | `design/` | `stories/` |
| **Project Initialiser** | Scaffolds `workspace/` before the first Coding Agent runs | `design/` | `workspace/` |
| **Coding Agent** (×N) | Claims and implements one story at a time | `stories/`, `workspace/CLAUDE.md` | `workspace/` |
| **Story Reviewer** | Triages permanently-failed stories with user guidance | `stories/*.failed.md` | `stories/` |

Each agent reads its system prompt from a file in `roles/`.

---

## Directory Layout

```
momo-agents/
├── design/                    ← Designer Agent outputs
│   └── <feature>.md
├── stories/                   ← story files; state encoded in filename suffix
│   ├── STORY-001.md           ← pending
│   ├── STORY-002.working.md   ← claimed by a Coding Agent
│   ├── STORY-003.done.md      ← complete
│   ├── STORY-004.failed.md    ← exhausted retries; awaiting review
│   ├── STORY-005.reviewing.md ← claimed by Story Reviewer
│   └── HALT                   ← sentinel: all Coding Agents must stop
├── roles/                     ← system prompt files
│   ├── designer.md
│   ├── business-analyst.md
│   ├── project-initialiser.md
│   ├── coding-agent.md
│   └── story-reviewer.md
├── status.sh                  ← prints a live summary of all story states
├── watchdog.sh                ← resets stories stuck in .working.md for > 10 min
└── workspace/                 ← generated source code (same repo)
    ├── CLAUDE.md              ← build/test/lint instructions for Coding Agents
    ├── src/
    └── tests/
```

---

## Story File Format

Every story file carries machine-readable header fields:

```markdown
# STORY-NNN: <Short Title>

**Index**: N          ← priority order; lower = worked first
**Attempts**: 0       ← incremented by each Coding Agent attempt; max 5
**Design ref**: design/<feature>.md
**Depends on**: STORY-NNN | none

## Context
## Acceptance Criteria
## Implementation Hints
## Test Requirements

---
<!-- Coding Agent appends timestamped failure notes below this line -->
```

A story with `**Depends on**: STORY-NNN` may only be claimed once that dependency is in `.done.md` state.

---

## Story Lifecycle

```
BA Agent writes
STORY-NNN.md  (Index: N, Attempts: 0)
      │
      │  Coding Agent checks: is dependency .done?
      │  If not → skip, try next story
      │  If yes → sort by Index, atomically claim lowest:
      ▼
STORY-NNN.working.md   ← owned by exactly one Coding Agent
      │                  Attempts incremented on claim
      │
   ┌──┴──────────────┐
success            failure
   │                   │
   ▼                   │ append failure note
STORY-NNN.done.md      │
(commit workspace)  Attempts < 5?
                    ├─ yes → rename back to STORY-NNN.md   (pending again)
                    └─ no  → create stories/HALT
                             rename to STORY-NNN.failed.md
                                  │
                           ◄──────┘  all other Coding Agents detect HALT:
                           │         revert uncommitted workspace changes
                           │         rename .working.md → .md
                           │         exit
                           │
                     Story Reviewer claims:
                     STORY-NNN.failed.md → STORY-NNN.reviewing.md
                           │
                     summarises attempts to user
                     waits for user guidance
                     rewrites story in full (Attempts reset to 0)
                           │
                     if no more .failed.md files: delete HALT
                     rename STORY-NNN.reviewing.md → STORY-NNN.md
                           │
                     Orchestrator re-spawns Coding Agents
```

---

## Story States

| Filename suffix | State | Who can claim it |
|---|---|---|
| `.md` | Pending | Any Coding Agent (dependency permitting) |
| `.working.md` | In progress (owned) | — |
| `.done.md` | Complete | Nobody |
| `.failed.md` | Exhausted retries | Story Reviewer Agent |
| `.reviewing.md` | Under review (owned) | — |
| `HALT` (sentinel) | System halted | Triggers stop + revert in all Coding Agents |

---

## Parallel Coordination

All coordination is via atomic filesystem operations — no database, no message queue.

**Claiming a story**: a Coding Agent renames `STORY-NNN.md` → `STORY-NNN.working.md`. POSIX `rename(2)` is atomic; if two agents race, exactly one succeeds and the other moves to the next story.

**Dependency check**: before claiming, the agent reads `**Depends on**` from each candidate story and skips any whose dependency is not yet `.done.md`. Skipped stories remain pending for when the dependency completes.

**Halt detection**: Coding Agents check for `stories/HALT` before claiming a new story and at key checkpoints during implementation (before writing files, before running tests). On detection they:
1. Discard all uncommitted workspace changes (`git checkout -- workspace/`)
2. Rename their `.working.md` back to `.md`
3. Exit

**Workspace commit policy**: Coding Agents do **not** commit workspace changes until a story is successfully completed and renamed `.done.md`. All in-progress work stays uncommitted, making git-based revert clean and safe.

**HALT removal**: The Story Reviewer deletes `stories/HALT` only after the last `.failed.md` has been resolved, ensuring Coding Agents do not resume until every failed story has been addressed.

---

## Retry Policy

| Attempts so far | On next failure |
|---|---|
| 1 – 4 | Append failure note; release story back to pending |
| 5 | Append failure note; create `HALT`; mark `.failed.md` |

A failure note records the attempt number, a UTC timestamp, and a summary of what went wrong. Notes accumulate in the story file and are read by the Story Reviewer to brief the user.

---

## Designer Agent Workflow

The Designer Agent runs interactively:

1. Opens a conversation with the user about their requirements.
2. Asks clarifying questions freely until it has a complete understanding.
3. Waits — it does **not** write anything until the user issues the command `write`.
4. On receiving `write`: produces the design document and saves it to `design/<feature>.md`.

This ensures the design reflects a deliberate, agreed specification rather than the agent's first interpretation.

---

## Project Initialiser Agent

Runs once, automatically, before the first Coding Agent is spawned. Responsibilities:

1. Reads the design document to understand the technology stack and project structure.
2. Creates `workspace/CLAUDE.md` describing build, test, and lint commands.
3. Scaffolds the initial project structure (directory layout, config files, empty entry points).
4. Does **not** implement any story logic.

Once it exits, the workspace is ready and Coding Agents may begin.

---

## Story Reviewer Workflow

1. Detects `stories/HALT` and one or more `.failed.md` files.
2. Atomically claims the next `.failed.md` → `.reviewing.md`.
3. Reads the full file including all failure notes.
4. Presents the user with:
   - The original story goal and acceptance criteria.
   - A plain-language summary of each failed attempt and what went wrong.
5. Asks the user how to proceed (new approach, relaxed constraints, split the story, etc.).
6. Replaces the **entire file content** with a clean rewritten story; resets `**Attempts**: 0`; preserves `**Index**` and `**Depends on**`.
7. If no more `.failed.md` files exist: deletes `stories/HALT`.
8. Renames `.reviewing.md` → `.md` — the story re-enters the pending queue.

---

## Watchdog (`watchdog.sh`)

Runs continuously alongside Coding Agents. Every 60 seconds it scans `stories/` for `.working.md` files and checks the file's last-modified timestamp. Any story that has been in `.working.md` state for more than **10 minutes** is assumed to belong to a dead or stalled agent and is reset:

```
STORY-NNN.working.md  →  STORY-NNN.md   (pending again)
```

The watchdog does not revert workspace changes — those are handled by the agent itself on halt detection, or remain as uncommitted noise until the next successful agent cleans up via `git checkout -- workspace/`.

---

## Observability (`status.sh`)

Prints a live count and list of stories in each state:

```
$ ./status.sh

  pending    2   STORY-001.md  STORY-004.md
  working    1   STORY-002.working.md
  done       3   STORY-003  STORY-005  STORY-006
  failed     0
  reviewing  0
  HALT       no
```

Run at any time to check pipeline progress.

---

## Orchestrator (`orchestrate.sh`)

```
1.  Designer Agent (interactive) → waits for user `write` command
                                 → design/<feature>.md
2.  BA Agent                     → stories/STORY-NNN.md (×N)
3.  Project Initialiser Agent    → workspace/ scaffold + CLAUDE.md
4.  Start watchdog.sh in background
5.  Spawn N Coding Agents in parallel; wait for all to exit
6.  Stop watchdog
7.  If stories/HALT exists:
      launch Story Reviewer (interactive, foreground)
      go to step 4
8.  Done — all stories are .done.md
```

The loop in steps 4–7 repeats until all stories are `.done.md` and no `HALT` file remains.
