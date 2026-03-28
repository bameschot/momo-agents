# momo-agents

A multi-agent coding pipeline powered by the Claude Agent SDK. A team of specialised agents collaborate over the filesystem to take a feature idea from concept through to working, tested code — without human intervention between steps.

---

## Pipeline overview

```
  You ──► Designer ──► Business Analyst ──► Project Initialiser
                                                    │
                                          ┌─────────┘
                                          ▼
                                  Coding Agent 1 ──┐
                                  Coding Agent 2 ──┼──► workspace/
                                  Coding Agent N ──┘
                                          │
                                  (on failure)
                                          ▼
                                   Story Reviewer ──► You
```

| Agent | Role |
|---|---|
| **Designer** | Interactive Q&A session with you. Produces `design/<feature>.new.md`. |
| **Business Analyst** | Watches `design/` for `*.new.md` files and decomposes each into ordered `stories/STORY-NNN.md` files. |
| **Project Initialiser** | Reads the design and scaffolds `workspace/` — directory layout, config files, dependency manifests, and `workspace/CLAUDE.md` with build/test/lint commands. |
| **Coding Agent** | Claims stories one at a time (by atomic rename), implements them inside `workspace/`, runs tests, and commits. Multiple instances run in parallel. |
| **Story Reviewer** | Wakes when a `HALT` file appears (a story failed 5 times). Triages the failure with you and resets the story so coding can resume. |
| **Watchdog** | Background process that resets any `.working.md` story stuck for more than 10 minutes back to pending, recovering from crashed agents. |

### Story lifecycle

Stories move through states encoded in their filename suffix:

```
STORY-NNN.md  →  STORY-NNN.working.md  →  STORY-NNN.done.md
                          │
                    (5 failures)
                          ▼
               STORY-NNN.failed.md  +  HALT
                          │
                  (Story Reviewer)
                          ▼
               STORY-NNN.reviewing.md  →  STORY-NNN.md  (reset)
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
| `--dev-agents N` | Number of parallel Coding Agents | `2` |
| `--model-designer M` | Claude model for the Designer | `claude-sonnet-4-6` |
| `--model-ba M` | Claude model for the Business Analyst | `claude-sonnet-4-6` |
| `--model-pi M` | Claude model for the Project Initialiser | `claude-sonnet-4-6` |
| `--model-coder M` | Claude model for each Coding Agent | `claude-sonnet-4-6` |
| `--model-reviewer M` | Claude model for the Story Reviewer | `claude-sonnet-4-6` |

**Examples:**

```bash
# Basic — 2 coding agents, all agents use the default model
./start-team.sh my-feature

# 4 coding agents
./start-team.sh my-feature --dev-agents 4

# Use a faster/cheaper model for coding, opus for design
./start-team.sh my-feature \
  --model-designer claude-opus-4-6 \
  --model-coder claude-haiku-4-5-20251001

# --flag=value form also works
./start-team.sh my-feature --dev-agents=3 --model-coder=claude-haiku-4-5-20251001
```

### Check pipeline status

```bash
./status.sh
```

Prints a snapshot of how many stories are in each state (pending / working / done / failed / reviewing) and whether a HALT is active.

### Shut down the team

Press **Ctrl+C** in the terminal where `start-team.sh` is running. This:

1. Writes `.sentinels/pipeline_complete` — all agent windows exit cleanly.
2. Kills the watchdog process.
3. Removes the `.sentinels/` directory.
4. Prints a final `./status.sh` summary.

---

## Clearing the workspace

### Reset stories only (keep generated code)

```bash
rm -f stories/STORY-*.md stories/HALT
```

### Full reset — wipe everything generated

```bash
# Remove all stories
rm -f stories/STORY-*.md stories/HALT

# Remove generated workspace (keeps workspace/CLAUDE.md skeleton if you want)
rm -rf workspace/src workspace/tests
# or to wipe the entire workspace:
rm -rf workspace/*

# Remove any processed/new design files
rm -f design/*.new.md design/*.processed.md
```

After a full reset, re-running `./start-team.sh <feature-name>` will go through the complete pipeline from scratch.

---

## Running agents individually

Each agent can also be invoked directly:

```bash
# Designer (interactive)
python python-agents/designer.py --model claude-sonnet-4-6

# Business Analyst
python python-agents/business_analyst.py \
  --design design/my-feature.md \
  --model claude-sonnet-4-6

# Project Initialiser
python python-agents/project_initialiser.py \
  --design design/my-feature.md \
  --model claude-sonnet-4-6

# Coding Agent
python python-agents/coding_agent.py \
  --model claude-sonnet-4-6

# Story Reviewer
python python-agents/story_reviewer.py \
  --model claude-sonnet-4-6
```

All path arguments default to the standard locations inside the repo root, so they can be omitted in normal use.

---

## Development

```bash
# Lint
ruff check .
ruff format .

# Type check
mypy python-agents/

# Tests
pytest
```
