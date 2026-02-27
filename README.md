# orglens

Organizational lens for AI agents — topology, grammar, state.

orglens gives AI agents (and humans) awareness of how your knowledge work is organized. It defines an opinionated **grammar** for entities (projects, research programs, experiments, clients) and artifacts (plans, logs, specs), then provides a CLI to discover, scaffold, and query them.

The core design principle: **never re-derive what you can read.** orglens materializes a topology snapshot so that every new agent session starts with full organizational awareness — no directory scanning required.

## Quick Start

```bash
pip install -e .

# Configure your docs root
mkdir -p ~/.config/orglens
echo 'docs_root: ~/path/to/your/docs' > ~/.config/orglens/config.yaml

# See what exists
orglens list
orglens status
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `orglens list [--type TYPE]` | List all entities, optionally filtered by type |
| `orglens status` | Show aggregated status across all entities |
| `orglens find ARTIFACT_TYPE [ENTITY]` | Find artifacts (plan, log, spec), optionally scoped |
| `orglens new TYPE NAME [TOPIC]` | Create a new entity or artifact with correct naming |
| `orglens snapshot [--stdout]` | Generate a topology snapshot (markdown) |

## Grammar

orglens uses a YAML grammar (`orglens/grammars/default.yaml`) that defines:

- **Entity types**: research-program, experiment, project, client — each with required files, subdirectories, and state files
- **Artifact types**: plan, log, spec — each with a naming pattern and target directory
- **Naming conventions**: `{NN}-{topic}-{MonDDYYYY}.md` for plans/logs, `{topic}.md` for specs

The grammar is data, not code — new entity and artifact types can be added without changing Python.

## Ecosystem

orglens is part of a two-tool ecosystem:

- **scad** (scoped-agent-dispatch) — computation layer: where and how agents run (sessions, Docker, execution context)
- **orglens** — knowledge layer: what exists and how it's organized (topology, grammar, state)

Together they form a complete agent infrastructure. Claude Code is the orchestrator.

## Status

- **v1** (current): Topology + grammar + markdown state + snapshot + awareness skill
- **v2** (planned): Org-mode backend for structured state tracking

## License

MIT
