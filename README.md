# orglens

Organizational lens for AI agents — units of work, and where they live.

A piece of work lives in several places at once: a folder of documents, a code repository somewhere else, agent sessions that ran in both. orglens makes the **unit of work** the thing, and lets it point at the places it lives. A unit declares itself in a small marker file naming its **homes**; everything else — its documents, its sessions, where it stands — is derived from those.

Two design principles. **Never re-derive what you can read**, so a snapshot is materialized and an agent starts knowing the shape of things. And **report, never gate**: a missing declaration makes something show up as undeclared, never invisible. The last time completeness decided existence, four real bodies of work vanished for months.

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
cat > ~/.config/orglens/config.yaml <<'EOF'
roots:
  - ~/path/to/your/docs
  - ~/path/to/your/code
EOF
```

`roots` are the directories orglens sweeps to find declarations. Usually your documents tree plus wherever your repositories are checked out — a unit's homes can span them. The older single-tree spelling, `docs_root: ~/path/to/your/docs`, still works and means one root.

Roots are an optimisation, not a boundary. A unit outside every root is not invisible; it is simply un-met, and the first time you work in it, it registers itself.

You can also set `grammar: /path/to/custom.yaml` in the config to use a custom grammar instead of the bundled default.

## Usage

```bash
# List all units, grouped by the kind each declares
orglens list
orglens list --type project

# Where every unit stands — derived facts beside the authored line
orglens status

# Find documents by kind, optionally scoped to one unit
orglens find plan
orglens find plan physics-priors
orglens find spec orglens

# Create a unit: a directory, and the declaration that names it. The path
# given is exactly where it lands — nothing is numbered for you.
orglens new docs/projects/my-tool --kind project
orglens new docs/research/physics-priors/expt-2-world-model --kind experiment --part-of physics-priors

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
| `orglens list [--type KIND]` | List all units, grouped by declared kind |
| `orglens status` | Where every unit stands, across all of its homes |
| `orglens find KIND [UNIT]` | Find documents of a kind, optionally scoped to one unit — never its nested units, which own their own |
| `orglens new PATH [--kind KIND] [--part-of UNIT]` | Create a unit: a directory, and the declaration that names it |
| `orglens declare PATH [--yes]` | Declare an existing directory as a unit, proposed from what it looks like |
| `orglens check` | Report where the tree has drifted. Reports only — never gates |
| `orglens snapshot [--stdout]` | Generate a topology snapshot (markdown) |
| `orglens reference [--out PATH]` | Render the grammar as the skill's vocabulary reference |
| `orglens view` | Render where everything stands as a page, and open it |
| `orglens start UNIT [--home NAME] [--prompt TEXT] [--agent NAME] [--dry-run]` | Start a session for a unit, attributed before its first turn |
| `orglens config UNIT [--workdir NAME] [--out PATH]` | Render a unit's homes into the scad config for a container |

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

Four skills install: `orglens`, plus `interior-viz`, `interior-design-book`
and `article` from the decks under `capabilities/`.

The CLI installs a skill *copy*, not a symlink, so **re-run the command after
editing a `SKILL.md`**. `references/grammar-reference.md` is generated — run
`orglens reference --out skills/orglens/references/grammar-reference.md`
before reinstalling, or the test suite will tell you it is stale.

orglens was previously a Claude Code plugin. It is not any more: a plugin
reaches exactly one agent, and these decks are built on the premise of dealing
different passes to different model families. If a machine still carries the old
registration, remove it before installing — plugin skills and directory skills
**stack rather than override**, so the same skill arrives twice, namespaced and
bare, with identical descriptions competing for one trigger.

## Declaring a unit

A unit is one body of effort with a goal — a project, a client engagement, a
research programme, an experiment. It declares itself in a `.orglens.yml` beside
its documents:

```yaml
unit: orglens
kind: project
part_of: traitful-workflow-ecosystem
homes:
  - orglens                                  # a code repository
  - traitful-docs/docs/projects/orglens      # its documents
```

`kind` is a label used for grouping and display; nothing behaves differently
because of it. `part_of` is the only way one unit belongs to another. `homes` are
named repositories, optionally with a path inside one — the marker's own
directory is always a home whether or not it is listed.

**Homes can be shared.** The same repository is genuinely a home of two units
when both work in it, and each sees its documents. That is normal, not a case to
design around.

Everything a unit needs to be found travels with it in git. `~/.orglens` holds an
index and a log of what happened — delete it and you lose speed and history,
never the definition of your work.

## Grammar

The grammar (`orglens/grammars/default.yaml`) says what documents are called and what each part of a unit is for. It no longer decides what *exists* — declarations do that — but its patterns still propose undeclared candidates. No database: the tree and the markers in it are the data, and `~/.orglens` holds only an index that can be thrown away and rebuilt.

The grammar has three blocks and nothing else:

```yaml
entities:                     # what *might* be undeclared work, as a relative glob
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
`skills/orglens/references/grammar-reference.md`.

The grammar is data, not code. Adding a kind is one line and needs no Python
change: `deck: capabilities/*` is a working example, exercised by
`capabilities/.orglens-grammar.yml`.

## How Discovery Works

1. **A unit exists because it declares itself**, not because of where its folder
   sits. Discovery sweeps the roots for `.orglens.yml` markers. Position carries
   no meaning any more — a unit can move without becoming something else
2. **Grouping is stated, never derived from nesting.** A unit says `part_of:
   <other unit>`. A folder inside another folder is not its child unless it says
   so, which is what lets work be regrouped with nothing renamed
3. The old positional patterns survive **demoted**, as a candidate detector: a
   directory matching `projects/*` with no declaration is reported as *undeclared
   work*, never hidden. That report is the migration worklist
4. **A home is named, not located.** A declaration says `world-model-ladder`, and
   the name resolves to a path here by a ladder — an explicit marker, then the
   git remote, then the directory name — with the rung that answered reported. So
   the same unit works on another machine, and inside a container, where its
   repositories sit at different paths
5. **Documents belong to a home by containment**, at any depth, minus whatever a
   nested unit's home claims. A `.md` file matching an artifact's `find` glob
   **is** a document of that kind, whatever it is called. Nothing parses a filename
6. **Sessions join by where they ran**, not by a name that happens to match. A
   session in any of a unit's homes is that unit's — which is how one body of
   work stops being two unrelated numbers

Status is the first line carrying a bolded `Status:` marker in blockquote form, found in a unit's documents,
looking at the ones `structure` names first. Nothing declares a state file, so
moving the line into whichever document you actually maintain works. It is
always reported with its age — an authored sentence can go stale, and a dated
quote is honest where a bare claim is not.

## How Sessions Get Attributed

"Sessions join by where they ran," above, answers for work done *inside* a
home and cannot answer for work done *above* one. At the root of a documents
repository with sixteen homes sitting below it, containment has nothing to
choose between; on the real tree, 108 sessions belong to no unit for exactly
that reason.

`orglens start UNIT` inverts the order rather than trying to guess it better
afterward: it records the unit *before* the session's first turn, so the
working directory becomes a consequence of that choice, not the evidence for
it. It picks one of the unit's homes — asking, with `--home`, when more than
one resolves — shells out to `scad session launch`, reads back the id scad
printed, and appends one `attributed` event to `~/.orglens/events/`. The
session also arrives already knowing what it is: unless you pass `--prompt`,
its first turn names the unit, lists every home, and points at wherever the
unit's status is authored, because on this machine every home is already
reachable — what a session lacks at the start is not access but knowledge.

Nothing here is guessed. A session is attributed because someone said so at
the moment it started, or because containment gives exactly one answer once
it's running. Sessions started any other way keep being attributed by
containment where that is unambiguous, and sit **unattributed** where it is
not — unattributed is a valid resting state, not a failure to fix.

`orglens start` folds in declaration: name a unit that has not been declared
yet, and it proposes one from what the directory looks like — kind from
where it sits, `part_of` from what contains it, a home from a same-named
repository — shows the reasoning behind each guess, and asks, because
starting work is the moment you actually know what the work is. `orglens
declare PATH` runs the same proposal on its own, for naming a directory
without starting anything in it.

`orglens config UNIT` has a second job the rest of this tree deliberately
avoids: it writes a file. Every other command here only *reads* scad's
records — `~/.scad/index.sqlite`, `~/.scad/launches/` — because scad owns
what happened and orglens only points at it. `config` is the one exception,
and it is narrow: it renders a unit's homes into the `repos:` block of the
config a container launcher reads, because that block *is* a unit's homes
with paths attached, and maintaining both by hand is the duplication this
model exists to delete. Homes absent from this machine are left out — a
container cannot mount what is not here. This is the container lane only;
launching on this machine, with `orglens start`, needs no config at all.

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
- **orglens** — knowledge layer: what the work *is*, and where it lives (units, homes, documents, state)

## Development

```bash
# Run tests
pip install pytest
python -m pytest tests/ -v

# Current: 538 tests
```

## Status

- **v1.3** (current): Attribution moves to the moment a session starts.
  `orglens start` records the unit before the first turn and launches through
  scad; `orglens declare` proposes a unit from what a directory looks like;
  `orglens config` renders a unit's homes into the config a container reads.
  Containment still decides where it can, and reports unattributed where it
  cannot
- **v1.2**: Units of work — a unit declares its homes and can span several
  repositories; documents belong by containment; sessions join by where they
  ran. Replaces discovery by folder position
- **v1.1**: Grammar, state aggregation, snapshot, CLI, skills shipped through the
  shared agent-skills convention, demo script
- **planned**: org-mode backend for structured state tracking

## License

MIT
