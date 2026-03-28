# momo-agents

A multi-agent coding pipeline powered by the Claude Agent SDK. A team of specialised agents collaborate over the filesystem to take a feature idea from concept through to working, tested code — without human intervention between steps.

---

## Pipeline overview

```
  You ──► Designer ──► Business Analyst ──► Project Initialiser
                              │
                      Story Orchestrator
                       (marks stories ready
                        when deps are met)
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
     Junior Coding Agent 1 ──┐   Senior Coding Agent 1 ──┐
     Junior Coding Agent 2 ──┼►  Senior Coding Agent 2 ──┼──► workspace/
           [easy]            │         [medium/hard]      │
                             └─────────────┬──────────────┘
                                     (on failure)
                                           ▼
                                    Story Reviewer ──► You
```

| Agent | Role |
|---|---|
| **Designer** | Interactive Q&A session with you. Produces `design/<feature>.new.md`. |
| **Business Analyst** | Watches `design/` for `*.new.md` files and decomposes each into `stories/STORY-NNN.md` files, each with a **Complexity** field (easy / medium / hard). |
| **Project Initialiser** | Reads the design and scaffolds `workspace/` — directory layout, config files, dependency manifests, and `workspace/CLAUDE.md` with build/test/lint commands. |
| **Story Orchestrator** | Watches `stories/` for new `STORY-NNN.md` files, parses their complexity and dependencies, and renames them to `STORY-NNN.[complexity].ready.md` when all dependencies are complete. |
| **Junior Coding Agent** | Claims and implements `easy` stories (`STORY-NNN.easy.ready.md`). Defaults to `claude-haiku`. Multiple instances run in parallel. |
| **Senior Coding Agent** | Claims and implements `medium` and `hard` stories. Defaults to `claude-sonnet`. Multiple instances run in parallel. |
| **Story Reviewer** | Wakes when a `HALT` file appears (a story failed 5 times). Triages the failure with you and resets the story so coding can resume. |
| **Watchdog** | Background process that resets any stale `.working.md` story (idle > 10 min) back to `.ready.md`, recovering from crashed agents. |

### Story lifecycle

Stories move through states encoded in their filename. The filename carries both the **complexity** and the **state**:

```
STORY-NNN.md              ← written by BA (unprocessed)
      │
  Story Orchestrator checks deps
      │
      ▼
STORY-NNN.[complexity].ready.md     ← deps met; ready to claim
      │
  Coding Agent atomically claims
      │
      ▼
STORY-NNN.[complexity].working.md   ← owned by one agent
      │
  ┌───┴────────────────────┐
success                 failure (append note)
  │                         │
  ▼                    Attempts < 5?
STORY-NNN.[complexity].done.md  ├─ yes → back to .ready.md
(commit workspace)              └─ no  → create HALT
                                         rename to .failed.md
                                              │
                                    Story Reviewer triages
                                    rewrites story → bare STORY-NNN.md
                                    Story Orchestrator re-evaluates
```

---

## Setup

### Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip`
- An Anthropic API key

### Install

```bash
# 1. Clone the repository
git clone https://github.com/bameschot/momo-agents.git
cd momo-agents

# 2. Create a virtual environment
uv venv
source .venv/bin/activate      # Linux / macOS

# 3. Install the project and its dependencies
uv pip install -e ".[dev]"

# 4. Add your API key
echo "ANTHROPIC_API_KEY=your_key_here" > .env
```

---

## Running the pipeline

### Start the full team

```bash
./start-team.sh <feature-name> [options]
```

This opens every agent simultaneously, each in its own terminal window, and then monitors the pipeline in the current terminal until you press **Ctrl+C**.

**Options:**

| Flag | Description | Default |
|---|---|---|
| `--junior-agents N` | Number of parallel Junior Coding Agents (easy stories) | `2` |
| `--senior-agents N` | Number of parallel Senior Coding Agents (medium/hard stories) | `1` |
| `--model-designer M` | Claude model for the Designer | `claude-sonnet-4-6` |
| `--model-ba M` | Claude model for the Business Analyst | `claude-sonnet-4-6` |
| `--model-pi M` | Claude model for the Project Initialiser | `claude-sonnet-4-6` |
| `--model-junior M` | Claude model for Junior Coding Agents | `claude-haiku-4-5-20251001` |
| `--model-senior M` | Claude model for Senior Coding Agents | `claude-sonnet-4-6` |
| `--model-reviewer M` | Claude model for the Story Reviewer | `claude-sonnet-4-6` |

**Examples:**

```bash
# Default — 2 junior agents, 1 senior agent
./start-team.sh my-feature

# Scale up for a large backlog
./start-team.sh my-feature --junior-agents 4 --senior-agents 2

# Use opus for design, keep defaults elsewhere
./start-team.sh my-feature --model-designer claude-opus-4-6

# --flag=value form also works
./start-team.sh my-feature --junior-agents=3 --model-junior=claude-sonnet-4-6
```

### Check pipeline status

```bash
./status.sh
```

Prints a snapshot of how many stories are in each state:

```
  unprocessed    2   STORY-001.md  STORY-004.md
  ready          1   STORY-002.easy.ready.md
  working        1   STORY-003.medium.working.md
  done           3   STORY-005.easy.done.md  ...
  failed         0
  reviewing      0
  HALT           no
```

### Shut down the team

Press **Ctrl+C** in the terminal where `start-team.sh` is running. This:

1. Writes `.sentinels/pipeline_complete` — all agent windows exit cleanly.
2. Kills the watchdog process.
3. Prints a final token-usage summary and `./status.sh` snapshot.
4. Removes the `.sentinels/` directory.

---

## Clearing the workspace

### Reset stories only (keep generated code)

```bash
rm -f stories/STORY-*.md stories/HALT
```

### Full reset — wipe everything generated

```bash
./reset-team.sh
# or skip the confirmation prompt:
./reset-team.sh --yes
```

After a full reset, re-running `./start-team.sh <feature-name>` will go through the complete pipeline from scratch.

---

## Running agents individually

Each agent can also be invoked directly:

```bash
# Designer (interactive)
python scripts/designer_agent.py --model claude-sonnet-4-6

# Business Analyst
python scripts/business_analyst_agent.py \
  --design design/my-feature.new.md \
  --model claude-sonnet-4-6

# Project Initialiser
python scripts/project_initialiser_agent.py \
  --design design/my-feature.new.md \
  --model claude-sonnet-4-6

# Story Orchestrator (marks stories ready as deps are met)
python scripts/story_orchestrator.py

# Junior Coding Agent (easy stories)
python scripts/junior_coding_agent.py \
  --model claude-haiku-4-5-20251001

# Senior Coding Agent (medium/hard stories)
python scripts/senior_coding_agent.py \
  --model claude-sonnet-4-6

# Story Reviewer
python scripts/story_reviewer_agent.py \
  --model claude-sonnet-4-6
```

All path arguments default to the standard locations inside the repo root.

---

## Development

```bash
# Lint
ruff check .
ruff format .

# Type check
mypy scripts/

# Tests
pytest
```
