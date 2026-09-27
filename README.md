# orglens

Organizational lens for AI agents — units of work, and where they live.

A piece of work lives in several places at once: a folder of documents, a code repository somewhere else, agent sessions that ran in both. orglens makes the **unit of work** the thing, and lets it point at the places it lives. A unit declares itself in a small marker file naming its **homes**; everything else — its documents, its sessions, where it stands — is derived from those.

## scad

orglens is built alongside [scad](https://github.com/saptaxis/scoped-agent-dispatch),
a lower-level tool that runs agent sessions and records what happened.

scad is optional and not a dependency. `orglens start` and `resume` shell out to
it, and sessions and notes come from `scad session ls --json` and `scad notes ls
--about` when it is present (scad 0.5 or later; an older scad or none means no
sessions, which is ordinary). Every other command works without it.

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
mkdir -p ~/.orglens
cat > ~/.orglens/config.yaml <<'EOF'
roots:
  - ~/path/to/your/docs
  - ~/path/to/your/code
EOF
```

`roots` are the directories orglens sweeps for declarations: your documents tree
and wherever your repositories are checked out. A unit outside every root is
un-met rather than invisible, and registers itself the first time you work in
it. The sweep goes three directories below each root; a marker deeper than
that is found by listing its parent as a root too. A root that is itself a
repository counts as a home candidate, so a checkout whose parent holds
everything can be listed on its own. `grammar: /path/to/custom.yaml`
replaces the bundled grammar.

## CLI Reference

| Command | Description |
|---------|-------------|
| `orglens list [--type KIND]` | List all units, grouped by declared kind |
| `orglens status` | Where every unit stands, across all of its homes |
| `orglens find KIND [UNIT] [--in DIR] [--grep TEXT] [--since 2w] [--waiting] [--json]` | Find documents of a kind, optionally scoped to one unit — never its nested units, which own their own. `--in` scopes to a directory the grammar has no name for; `--grep` keeps the ones whose text matches and shows the lines |
| `orglens new PATH [--kind KIND] [--part-of UNIT] [--home NAME]` | Create a unit: a directory, and the declaration that names it. `--home` is repeatable |
| `orglens declare PATH [--yes]` | Declare an existing directory as a unit, proposed from what it looks like |
| `orglens check` | Report where the tree has drifted: missing driver documents, undeclared folders, weak or shared homes, kinds that match nothing, folders of documents the grammar has no word for. Reports only — never gates |
| `orglens snapshot [--stdout] [--check]` | Generate a topology snapshot (markdown); `--check` says whether the written one is older than any declaration or driver document, exit 1 if so |
| `orglens reference [--out PATH]` | Render the grammar as the skill's vocabulary reference |
| `orglens view` | Render where everything stands as a page, and open it: units banded by when they last moved, waiting first, a foldable card each; filter by band, kind, agent or text |
| `orglens start UNIT [--home NAME] [--prompt TEXT] [--agent NAME] [--window] [--about WORDS] [--name TEXT] [--dry-run]` | Start a session for a unit, attributed before its first turn; `--window` puts it in the tmux you are in, and the session is named `unit[-context]-sepDD` |
| `orglens sessions [UNIT] [--none] [--all] [--json]` | A unit's sessions, or every unit's grouped, newest first; `--none` lists the ones belonging to no unit |
| `orglens sessions --triage [--one-by-one]`, `--groups`, `--from FILE` | Decide the unclaimed sessions by directory, one at a time, or from a `--none --json` file you edited |
| `orglens notes [UNIT] [--no-mentions]` | What was written down about a unit, and why each note is the unit's |
| `orglens resume UNIT\|SESSION-ID [--prompt TEXT] [--print]` | Resume a session, or a unit's newest open one; `--prompt` sends a turn to it instead |
| `orglens attribute SESSION-ID UNIT [--why TEXT]` | Say which unit a session was for, after the fact |
| `orglens dismiss SESSION-ID\|--under PATH [--why TEXT]` | Say a session, or every unclaimed one under a path, belongs to no unit |
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

Everything needed to find a unit travels with it in git. `~/.orglens` holds the
config, a snapshot cache and the event log; deleting it loses your roots, speed
and attribution history, not the definition of your work.

## Grammar

The grammar (`orglens/grammars/default.yaml`) says what documents are called and
what each part of a unit is for. Its patterns propose undeclared candidates.
There is no database: the tree and its markers are the data, and `~/.orglens`
holds an index that can be deleted and rebuilt.

Documents are written directly, not through the CLI. Nothing parses a filename,
so nothing can compute one.

The grammar has three blocks, and two lines above them: `driver`, the one
document every unit carries, and `format`, the one `new` writes.

```yaml
driver: overview
format: md                    # or org: what `orglens new` writes

entities:                     # what *might* be undeclared work, as a relative glob
  project: projects/*
  experiment: expt-*

artifacts:                    # where documents live, and what to call new ones
  plan:
    find: plans/*
    means: A numbered unit of work, written before doing it. NN-topic-MonDDYYYY.

structure:                    # what each part is for. Authoring, never discovery.
  project:
    overview: What it is, its stack, and where its state lives.
```

The grammar is data. Adding a kind is one line and needs no Python change:
`capability: "*"` is a working example, exercised by
`capabilities/.orglens-grammar.yml`. A rendering of the grammar lives at
`skills/orglens/references/grammar-reference.md`.

## Formats

orglens reads markdown and org, mixed in one tree. The grammar's `format:`
(`md` by default, or `org`) decides only what `orglens new` writes. Patterns
name no extension: `plans/*` matches `plans/01-x.md` and `plans/02-y.org`,
and never an image or a `.nav.yml`. In org the status line is a `#+STATUS:`
keyword; in markdown it is `> **Status:**`. When one document exists in both
formats side by side, the grammar's format is read and `check` reports the pair.

## How Discovery Works

1. **Positional patterns detect candidates.** A directory matching `projects/*`
   with no declaration is reported as undeclared work
2. **Documents belong to a home by containment**, at any depth, minus whatever a
   nested unit's home claims. A document (`.md` or `.org`) matching an artifact's `find` glob
   **is** a document of that kind, whatever it is called
3. **Sessions join by where they ran.** A session in any of a unit's homes
   counts for that unit

Status is the first status line (`> **Status:**` in markdown, `#+STATUS:` in
org) in a unit's documents, looking at the
ones `structure` names first. Nothing declares a state file, so
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
is also how a shared-home session is narrowed to one unit. `orglens dismiss`
says a session is nobody's, which is what lets the unclaimed pile empty;
`sessions --triage` walks that pile by directory, one answer per group, and
`sessions --from FILE` applies the same decisions written into a
`--none --json` file. Neither proposes a unit: a session at a shared root could
be any of the units under it, and guessing from its title is the containment
mistake one layer up.

`orglens notes UNIT` prints what was written down about it. A note is the
unit's because the session that wrote it is (`written here`), because scad
filed it there (`filed here`), or because it names the unit (`mentions this`);
each row says which.

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
This is the only command that writes under `~/.scad`; nothing else in orglens
touches that directory, and scad's index is never opened — sessions and notes
come through scad's own commands. Launching on this machine needs no config.

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
```

`skills/orglens/references/grammar-reference.md` is generated. Run
`orglens reference --out skills/orglens/references/grammar-reference.md`
after changing the grammar; the test suite reports it when stale.

## License

MIT
