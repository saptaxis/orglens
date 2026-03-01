# orglens

Organizational lens for AI agents — topology, grammar, state.

orglens gives AI agents (and humans) awareness of how your knowledge work is organized. It defines an opinionated **grammar** for entities (projects, research programs, experiments, clients) and artifacts (plans, logs, specs), then provides a CLI to discover, scaffold, and query them.

The core design principle: **never re-derive what you can read.** orglens materializes a topology snapshot so that every new agent session starts with full organizational awareness — no directory scanning required.

## Install

Requires Python 3.11+.

```bash
# Clone and install in a virtualenv
git clone https://github.com/vignesh-saptarishi/orglens.git
cd orglens
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Configure

orglens needs to know where your docs tree lives:

```bash
mkdir -p ~/.config/orglens
echo 'docs_root: ~/path/to/your/docs' > ~/.config/orglens/config.yaml
```

The `docs_root` should point to a directory containing subdirectories like `projects/`, `research/`, `clients/` — each holding entities that follow the grammar.

You can also set `grammar: /path/to/custom.yaml` in the config to use a custom grammar instead of the bundled default.

## Usage

```bash
# List all entities (projects, research programs, clients)
orglens list
orglens list --type project

# Show status across all entities
orglens status

# Find artifacts by type, optionally scoped to an entity
orglens find plan
orglens find plan physics-priors
orglens find spec orglens

# Create a new entity
orglens new project my-tool
orglens new experiment world-model --parent physics-priors

# Create a new artifact (auto-numbers, auto-dates)
orglens new plan my-tool "feature-design"
orglens new log my-tool "feature-design"
orglens new spec my-tool "api-reference"

# Generate a topology snapshot
orglens snapshot              # writes to ~/.config/orglens/cache/snapshot.md
orglens snapshot --stdout     # prints to stdout
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `orglens list [--type TYPE]` | List all entities, optionally filtered by type |
| `orglens status` | Show aggregated status across all entities |
| `orglens find ARTIFACT_TYPE [ENTITY]` | Find artifacts (plan, log, spec), optionally scoped |
| `orglens new TYPE NAME [TOPIC]` | Create a new entity or artifact with correct naming |
| `orglens snapshot [--stdout]` | Generate a topology snapshot (markdown) |

## Grammar

orglens discovers entities by scanning the filesystem against a YAML grammar (`orglens/grammars/default.yaml`). No registry or database — the directory tree is the data.

**Entity types** define what lives where:

| Type | Location | Required files | Subdirectories |
|------|----------|----------------|----------------|
| research-program | `research/` | `research-question.md`, `research-program-state.md` | `specs/`, `literature/`, `directions/`, `brainstorms/` |
| experiment | `research/<program>/expt-{n}-{name}/` | `design.md` | `plans/`, `logs/`, `findings/` |
| project | `projects/` | `overview.md` | `specs/`, `plans/`, `logs/` |
| client | `clients/` | `overview.md` | — |

**Artifact types** define naming patterns:

| Type | Directory | Pattern | Example |
|------|-----------|---------|---------|
| plan | `plans/` | `{NN}-{topic}-{MonDDYYYY}.md` | `05-data-collection-Feb062026.md` |
| log | `logs/` | `{NN}-{topic}-{MonDDYYYY}-log.md` | `05-data-collection-Feb062026-log.md` |
| spec | `specs/` | `{topic}.md` | `system-design-v2.md` |

The grammar is data, not code — entity and artifact types can be added or changed without modifying Python.

## How Discovery Works

1. For each entity type, orglens looks in `docs_root/<parent_dir>/` (e.g. `docs_root/projects/`)
2. Each subdirectory that contains the required files is recognized as an entity
3. For experiments, it looks inside research programs for dirs matching `expt-*`
4. Artifacts are found by matching filenames in the artifact's target directory against its naming pattern

Status is extracted from `> **Status:** ...` badges in entity state files (e.g. `overview.md`).

## Ecosystem

orglens is part of a two-tool ecosystem:

- **scad** (scoped-agent-dispatch) — computation layer: where and how agents run (sessions, Docker, execution context)
- **orglens** — knowledge layer: what exists and how it's organized (topology, grammar, state)

## Development

```bash
# Run tests
pip install pytest
python -m pytest tests/ -v

# Current: 82 tests
```

## Status

- **v1** (current): Grammar, topology, state aggregation, snapshot, CLI, awareness skill
- **v2** (planned): Org-mode backend for structured state tracking

## License

MIT
