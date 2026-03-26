# Momo Agents — System Design Summary

## What It Is

A multi-agent coding team built on the Claude Code CLI. The user describes what they want; a pipeline of specialised agents turns that into a design, breaks it into stories, implements the stories in parallel, and escalates to the user only when something is truly stuck.

---

## Agents and Their Roles

| Agent | Role | Reads from | Writes to |
|---|---|---|---|
| **Designer** | Turns user requirements into a structured design document | User input | `design/` |
| **Business Analyst** | Breaks a design into ordered, discrete stories | `design/` | `stories/` |
| **Coding Agent** (×N) | Claims and implements one story at a time | `stories/`, `workspace/CLAUDE.md` | `workspace/` |
| **Story Reviewer** | Triages permanently-failed stories with user guidance | `stories/*.failed.md` | `stories/` |

Each agent reads its system prompt from a file in `roles/` (`roles/designer.md`, `roles/business-analyst.md`, `roles/coding-agent.md`, `roles/story-reviewer.md`).

---

## Directory Layout

```
momo-agents/
├── design/                   ← Designer Agent outputs
│   └── <feature>.md
├── stories/                  ← story files; state encoded in filename suffix
│   ├── STORY-001.md          ← pending
│   ├── STORY-002.working.md  ← claimed by a Coding Agent
│   ├── STORY-003.done.md     ← complete
│   ├── STORY-004.failed.md   ← exhausted retries; awaiting review
│   ├── STORY-005.reviewing.md← claimed by Story Reviewer
│   └── HALT                  ← sentinel: all Coding Agents must stop
├── roles/                    ← system prompt files
│   ├── designer.md
│   ├── business-analyst.md
│   ├── coding-agent.md
│   └── story-reviewer.md
└── workspace/                ← generated source code (same repo)
    ├── CLAUDE.md             ← build/test/lint instructions for Coding Agents
    ├── src/
    └── tests/
```

---

## Story File Format

Every story file carries two machine-readable header fields:

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

---

## Story Lifecycle

```
BA Agent writes
STORY-NNN.md  (Index: N, Attempts: 0)
      │
      │  Coding Agent reads all pending stories,
      │  sorts by Index, atomically renames lowest:
      ▼
STORY-NNN.working.md   ← owned by exactly one Coding Agent
      │                  Attempts incremented on claim
      │
   ┌──┴──────────────┐
success            failure
   │                   │
   ▼                   │ append failure note
STORY-NNN.done.md      │
                  Attempts < 5?
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
| `.md` | Pending | Any Coding Agent |
| `.working.md` | In progress (owned) | — |
| `.done.md` | Complete | Nobody |
| `.failed.md` | Exhausted retries | Story Reviewer Agent |
| `.reviewing.md` | Under review (owned) | — |
| `HALT` (sentinel) | System halted | Triggers stop + revert in all Coding Agents |

---

## Parallel Coordination

All coordination is via atomic filesystem operations — no database, no message queue.

**Claiming a story**: a Coding Agent renames `STORY-NNN.md` → `STORY-NNN.working.md`. POSIX `rename(2)` is atomic; if two agents race, exactly one succeeds and the other moves to the next story.

**Halt detection**: Coding Agents check for `stories/HALT` before claiming a new story and at key checkpoints during implementation (before writing files, before running tests). On detection they:
1. Discard all uncommitted workspace changes (`git checkout -- workspace/`)
2. Rename their `.working.md` back to `.md`
3. Exit

**Workspace commit policy**: Coding Agents do **not** commit workspace changes until a story is successfully completed. All in-progress work is uncommitted, making git-based revert clean and safe.

**HALT removal**: The Story Reviewer deletes `stories/HALT` only after the last `.failed.md` has been resolved, ensuring Coding Agents do not resume until every failed story has been addressed.

---

## Retry Policy

| Attempts so far | On next failure |
|---|---|
| 1 – 4 | Append failure note; release story back to pending |
| 5 | Append failure note; create `HALT`; mark `.failed.md` |

A failure note records the attempt number, a UTC timestamp, and a summary of what went wrong. The notes accumulate in the story file and are read by the Story Reviewer to brief the user.

---

## Story Reviewer Workflow

1. Detects `stories/HALT` and one or more `.failed.md` files.
2. Atomically claims the next `.failed.md` → `.reviewing.md`.
3. Reads the full file including all failure notes.
4. Presents the user with:
   - The original story goal and acceptance criteria.
   - A plain-language summary of each failed attempt.
5. Asks the user how to proceed (rewrite approach, relax constraints, split the story, etc.).
6. Replaces the **entire file content** with a clean rewritten story; resets `**Attempts**: 0`; preserves `**Index**`.
7. If no more `.failed.md` files exist: deletes `stories/HALT`.
8. Renames `.reviewing.md` → `.md` — the story re-enters the pending queue.

---

## Orchestrator (`orchestrate.sh`)

```
1. Designer Agent    → design/<feature>.md
2. BA Agent          → stories/STORY-NNN.md (×N)
3. Spawn N Coding Agents in parallel; wait for all to exit
4. If stories/HALT exists:
     launch Story Reviewer (interactive, foreground)
     go to step 3
5. Done
```

The loop in steps 3–4 repeats until all stories are `.done.md` and no `HALT` file remains.

---

## Open Questions

1. **Story dependencies** — is `**Index**` ordering sufficient to enforce dependency sequencing, or should Coding Agents explicitly check that a dependency story is `.done` before starting?
2. **Designer interaction** — interactive clarifying Q&A vs. single-pass draft with open questions left in the document?
3. **Workspace initialisation** — who creates `workspace/CLAUDE.md` and the initial project scaffold before the first Coding Agent runs?
4. **Observability** — a `status.sh` helper that prints a live summary of story states would help operators monitor long runs.
5. **Stale `.working.md` files** — if a Coding Agent process is killed (not gracefully halted), its story stays in `.working.md` forever. A watchdog or manual recovery step (`mv STORY-NNN.working.md STORY-NNN.md`) is needed.
