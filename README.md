# orglens

Organizational lens for AI agents — topology, grammar, state.

orglens gives AI agents (and humans) awareness of how your knowledge work is organized. It defines an opinionated **grammar** for entities (projects, research programs, experiments, clients) and artifacts (plans, logs, specs), then provides a CLI to discover, scaffold, and query them.

The core design principle: **never re-derive what you can read.** orglens materializes a topology snapshot so that every new agent session starts with full organizational awareness — no directory scanning required.

## Install

Requires Python 3.11+.

```bash
# Clone and install in a virtualenv
git clone git@github.com:saptaxis/orglens.git
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

# Create a new entity — the name is given in full; nothing is numbered for you
orglens new project my-tool
orglens new experiment expt-2-world-model --parent physics-priors

# Report where the tree has drifted from the grammar. Reports only.
orglens check

# Generate a topology snapshot
orglens snapshot              # writes to ~/.config/orglens/cache/snapshot.md
orglens snapshot --stdout     # prints to stdout
```

Documents are written directly, not through the CLI. Nothing parses a filename,
so nothing can compute one — the grammar describes how to name a plan and you
write it.

## CLI Reference

| Command | Description |
|---------|-------------|
| `orglens list [--type TYPE]` | List all entities, optionally filtered by type |
| `orglens status` | Show aggregated status across all entities |
| `orglens find KIND [ENTITY]` | Find documents of a kind, optionally scoped to an entity and its children |
| `orglens new TYPE NAME [--parent ENTITY]` | Create an entity and whatever the grammar says it holds |
| `orglens check` | Report where the tree has drifted. Reports only — never gates |
| `orglens snapshot [--stdout]` | Generate a topology snapshot (markdown) |
| `orglens reference [--out PATH]` | Render the grammar as the skill's vocabulary reference |
| `orglens view` | Render where everything stands as a page, and open it |

## Skills

orglens ships its skills through the shared agent-skills convention, so Claude,
Codex, Kimi and anything else following it get the same files:

```bash
npx skills add . -g -a '*' -y --full-depth
```

That routes to `~/.agents/skills` (the shared convention) and `~/.claude/skills`
(Claude, which does not read the shared one). Letting the tool own the path
table is deliberate — a wrong skills path fails **silently**, with files present
that never load.

Four skills install: `org-context`, plus `interior-viz`, `interior-design-book`
and `article` from the decks under `capabilities/`.

The CLI installs a skill *copy*, not a symlink, so **re-run the command after
editing a `SKILL.md`**. `references/grammar-reference.md` is generated — run
`orglens reference --out skills/org-context/references/grammar-reference.md`
before reinstalling, or the test suite will tell you it is stale.

orglens was previously a Claude Code plugin. It is not any more: a plugin
reaches exactly one agent, and these decks are built on the premise of dealing
different passes to different model families. If a machine still carries the old
registration, remove it before installing — plugin skills and directory skills
**stack rather than override**, so the same skill arrives twice, namespaced and
bare, with identical descriptions competing for one trigger.

## Grammar

orglens discovers entities by scanning the filesystem against a YAML grammar (`orglens/grammars/default.yaml`). No registry or database — the directory tree is the data.

The grammar has three blocks and nothing else:

```yaml
entities:                     # what exists, as a relative glob
  project: projects/*
  experiment: expt-*

artifacts:                    # where documents live, and what to call new ones
  plan:
    find: plans/*.md
    means: A numbered unit of work, written before doing it. NN-topic-MonDDYYYY.md.

structure:                    # what each part is for. Authoring, never discovery.
  project:
    overview.md: What it is, its stack, and where its state lives.
```

The tables that used to be here are gone on purpose: they were a fourth copy of
the same vocabulary, and the copies drifted. **The grammar is the declaration**
— read `orglens/grammars/default.yaml`, or the rendering of it at
`skills/org-context/references/grammar-reference.md`.

The grammar is data, not code. Adding a kind is one line and needs no Python
change: `deck: capabilities/*` is a working example, exercised by
`capabilities/.orglens.yml`.

## How Discovery Works

1. Every entity pattern is **relative**: matched at the docs root, then inside
   every entity found, until nothing new turns up
2. An entity's parent is whichever entity contains it, so nesting is never
   declared — a client can grow projects and a project can grow experiments
   with no grammar edit
3. A directory that matches **is** an entity, whether or not it holds what
   `structure` describes. Completeness is never a precondition for visibility
4. A `.md` file matching an artifact's `find` glob **is** a document of that
   kind, whatever it is called. Nothing parses a filename

Status is the first `> **Status:** ...` line found in an entity's documents,
looking at the ones `structure` names first. Nothing declares a state file, so
moving the line into whichever document you actually maintain works. It is
always reported with its age — an authored sentence can go stale, and a dated
quote is honest where a bare claim is not.

## Demo

Run the included demo to validate the full flow:

```bash
./demo.sh          # interactive walkthrough (6 steps)
./demo.sh 3        # run a single step
```

Steps: install, configure, CLI commands, snapshot, skills, test suite.

## Ecosystem

orglens is part of a two-tool ecosystem:

- **scad** (scoped-agent-dispatch) — computation layer: where and how agents run (sessions, Docker, execution context)
- **orglens** — knowledge layer: what exists and how it's organized (topology, grammar, state)

## Development

```bash
# Run tests
pip install pytest
python -m pytest tests/ -v

# Current: 386 tests
```

## Status

- **v1.1** (current): Grammar, topology, state aggregation, snapshot, CLI, skills shipped through the shared agent-skills convention, demo script
- **v2** (planned): Org-mode backend for structured state tracking

## License

MIT
