# orglens

Organizational lens for AI agents — units of work, and where they live.

A piece of work lives in several places at once: a folder of documents, a code repository somewhere else, agent sessions that ran in both. orglens makes the **unit of work** the thing, and lets it point at the places it lives. A unit declares itself in a small marker file naming its **homes**; everything else — its documents, its sessions, where it stands — is derived from those.

## scad

orglens is built alongside [scad](https://github.com/saptaxis/scoped-agent-dispatch),
a lower-level tool that runs agent sessions and records what happened.

scad is optional and not a dependency. `orglens start` shells out to it to launch
a session, and session counts are read from its index when it is present. Every
other command works without it.

## What it assumes

- **A unit declares itself.** A `.orglens.yml` says what this is. Where the
  folder sits means nothing, so work can move without becoming something else.
- **Grouping is stated.** `part_of:` is the only way one unit belongs to
  another. A folder inside a folder is not its child.
- **A home is a name.** It resolves to a path on this machine — by marker, then
  git remote, then directory name — so one declaration works on your laptop,
  another machine, and inside a container where the repositories sit elsewhere.
- **Nothing is guessed.** A session belongs to a unit because someone said so,
  or because it ran inside one of the unit's homes. A session in a shared home
  belongs to each unit sharing it; a session above every home belongs to none,
  which is a resting state.
- **Declarations decide what exists.** The grammar's patterns only propose
  candidates worth asking about, and roots are where it looks rather than what
  exists.
- **Report, never gate.** A missing declaration makes something show up as
  undeclared. A completeness filter once hid four units for months.
- **Never re-derive what you can read.** The snapshot is materialised, so an
  agent starts knowing the shape of things instead of sweeping for it.

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

`roots` are the directories orglens sweeps for declarations: your documents tree
and wherever your repositories are checked out. A unit outside every root is
un-met rather than invisible, and registers itself the first time you work in
it. The sweep goes three directories below each root; a marker deeper than
that is found by listing its parent as a root too. `grammar: /path/to/custom.yaml`
replaces the bundled grammar.

## CLI Reference

| Command | Description |
|---------|-------------|
| `orglens list [--type KIND]` | List all units, grouped by declared kind |
| `orglens status` | Where every unit stands, across all of its homes |
| `orglens find KIND [UNIT]` | Find documents of a kind, optionally scoped to one unit — never its nested units, which own their own |
| `orglens new PATH [--kind KIND] [--part-of UNIT] [--home NAME]` | Create a unit: a directory, and the declaration that names it. `--home` is repeatable |
| `orglens declare PATH [--yes]` | Declare an existing directory as a unit, proposed from what it looks like |
| `orglens check` | Report where the tree has drifted. Reports only — never gates |
| `orglens snapshot [--stdout]` | Generate a topology snapshot (markdown) |
| `orglens reference [--out PATH]` | Render the grammar as the skill's vocabulary reference |
| `orglens view` | Render where everything stands as a page, and open it |
| `orglens start UNIT [--home NAME] [--prompt TEXT] [--agent NAME] [--dry-run]` | Start a session for a unit, attributed before its first turn |
| `orglens sessions [UNIT] [--none] [--all]` | A unit's sessions, or every unit's grouped, newest first; `--none` lists the ones belonging to no unit |
| `orglens resume UNIT\|SESSION-ID [--print]` | Resume a session, or a unit's newest open one, through `scad session resume` |
| `orglens attribute SESSION-ID UNIT` | Say which unit a session was for, after the fact |
| `orglens config UNIT [--workdir NAME] [--out PATH]` | Render a unit's homes into the scad config for a container |
| `orglens where [NAME]` | Which roots are configured, and which unit a name or this directory resolves to |
| `orglens workflow next\|done\|note\|goto PACKET` | Run a capability's workflow over a packet, one pass at a time, with a human between. See `capabilities/tutorial/README.md` |

## Skills

orglens ships `orglens` and `orglens-adapt` as agent skills. `bootstrap` installs
them:

```bash
./bootstrap
```

Capabilities about work that cannot be published live in a second repo and install the
same way:

```bash
./bootstrap --extras ~/code/orglens-extras
```

Skills install as copies, so re-run `bootstrap` after editing a `SKILL.md`. See
[`capabilities/README.md`](capabilities/README.md) for the capability layout.

## Declaring a unit

A unit is one body of effort with a goal — a project, a client engagement, a
research programme, an experiment. It declares itself in a `.orglens.yml` beside
its documents:

```yaml
unit: lunar-lander
kind: project
part_of: physics-priors
homes:
  - lunar-lander                       # a code repository
  - docs/projects/lunar-lander         # its documents
```

`kind` is a label used for grouping and display; nothing behaves differently
because of it. `part_of` is the only way one unit belongs to another. `homes` are
named repositories, optionally with a path inside one — the marker's own
directory is always a home whether or not it is listed.

Homes can be shared: one repository is a home of two units when both work in it,
and each sees its own documents. Inside a shared home, `where` answers the first
of those units by name; `check` reports every shared home and which unit that is.

Everything needed to find a unit travels with it in git. `~/.orglens` holds an
index and an event log; deleting it loses speed and attribution history, not the
definition of your work.

## Grammar

The grammar (`orglens/grammars/default.yaml`) says what documents are called and
what each part of a unit is for. Its patterns propose undeclared candidates.
There is no database: the tree and its markers are the data, and `~/.orglens`
holds an index that can be deleted and rebuilt.

Documents are written directly, not through the CLI. Nothing parses a filename,
so nothing can compute one.

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

The grammar is data. Adding a kind is one line and needs no Python change:
`capability: "*"` is a working example, exercised by
`capabilities/.orglens-grammar.yml`. A rendering of the grammar lives at
`skills/orglens/references/grammar-reference.md`.

## How Discovery Works

1. **Positional patterns detect candidates.** A directory matching `projects/*`
   with no declaration is reported as undeclared work
2. **Documents belong to a home by containment**, at any depth, minus whatever a
   nested unit's home claims. A `.md` file matching an artifact's `find` glob
   **is** a document of that kind, whatever it is called
3. **Sessions join by where they ran.** A session in any of a unit's homes
   counts for that unit

Status is the first line carrying a bolded `Status:` marker in blockquote form, found in a unit's documents,
looking at the ones `structure` names first. Nothing declares a state file, so
moving the line into whichever document you actually maintain works. It is
always reported with its age, since an authored sentence can go stale.

## How Sessions Get Attributed

A session belongs to a set of units. An explicit attribution names one unit, and
the session is that unit's alone. Otherwise the session belongs to every unit
with a home containing its working directory: one unit ordinarily, two when a
home is shared, none when it ran above every home. At the root of a documents
repository with sixteen homes below it, that is most of the sessions.

`orglens sessions UNIT` lists a unit's sessions and how each is the unit's;
`orglens sessions --none` lists the ones that belong to no unit. `orglens resume`
hands a session id, or a unit's newest open session, to `scad session resume`.
`orglens attribute SESSION-ID UNIT` records an attribution after the fact, which
is also how a shared-home session is narrowed to one unit.

`orglens start UNIT` records the unit before the session's first turn. It picks
one of the unit's homes, asking with `--home` when more than one resolves,
shells out to `scad session launch`, reads the session id from scad's output,
and appends one `attributed` event to `~/.orglens/events/`. Unless you pass
`--prompt`, the session's first turn names the unit, lists every home, and
points at wherever the unit's status is authored.

`orglens start` on an undeclared name proposes a declaration from the
directory's position: kind from where it sits, `part_of` from what contains it,
a home from a same-named repository. It shows the reasoning for each guess and
asks before writing. `orglens declare PATH` runs the same proposal without
starting a session.

`orglens config UNIT` renders a unit's homes into the `repos:` block of the
config a container launcher reads. Homes absent from this machine are left out.
This is the only command that writes under `~/.scad`; the others read
`~/.scad/index.sqlite` and `~/.scad/launches/`. Launching on this machine needs
no config.

## Demo

Six steps: install, configure, CLI commands, snapshot, skills, test suite.

```bash
DOCS_ROOT=~/path/to/your/docs ./demo.sh      # all six
DOCS_ROOT=~/path/to/your/docs ./demo.sh 3    # one step
```

## Development

```bash
# Run tests
pip install pytest
python -m pytest tests/ -v

# Current: 488 tests
```

`skills/orglens/references/grammar-reference.md` is generated. Run
`orglens reference --out skills/orglens/references/grammar-reference.md`
after changing the grammar; the test suite reports it when stale.

## License

MIT
