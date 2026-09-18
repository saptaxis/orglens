---
name: orglens
description: >
  Use when a session touches the documents tree or a unit of work: "what
  projects exist", "where does this plan go", "what is the status of X",
  "create a plan/spec/log for X", "start a new project", "which sessions
  belong to X", "resume the last session on X", "start a session on X", "run
  the next node", "what is waiting on me". Also on the words orglens, unit,
  home, packet, workflow, snapshot. Not for a code-only session inside one
  repository, and not inside a container mid-implementation.
---

# orglens — operator card

Announce: "Using orglens to <what>."

Every command an agent runs, once, with its one non-obvious fact. The common
path needs no `--help`. What is not here is in `~/Dropbox/code/orglens/README.md`
(source: `~/Dropbox/code/orglens/`; not importable from system python — it
lives in its own venv, and the CLI is `orglens` on PATH).

<HARD-GATE>
Never `ls`, `find`, `glob` or `tree` the documents tree to discover units,
homes, plans, specs or logs, and never `cat` a sibling's document to learn a
shape. `orglens list`, `find`, `sessions` and the snapshot answer the first;
this card and `orglens-adapt` answer the second. A scan sees folders, not
declarations, and a folder is not a unit until a marker says so. A document's
*contents* you read directly, once you know its path.
</HARD-GATE>

## Not for

A session that only edits code in one repository and never asks where the
work is filed. A container running one node of a workflow. Writing prose —
that is the writing capability's; this card only says where the file goes.

## Session start

```bash
orglens snapshot --check || orglens snapshot   # refresh only when stale
orglens snapshot --stdout --type project        # scope it: a projects task need not load every client and experiment
orglens snapshot --stdout --unit <name>         # one unit and its parts
```

The snapshot is the tree as one document. `--type`/`--unit` narrow it; the
unscoped one is 500+ lines. The grammar's own words for what may exist are in
`references/grammar-reference.md`, generated, never restated here.

## Find

```bash
orglens list [--type KIND]                      # units, grouped by kind, newest first
orglens status                                  # where each stands: status line, git, sessions, gates
orglens find plan <unit>                        # documents of a kind; a nested unit's own home is excluded
orglens find spec <unit> --grep "text"          # the ones that mention it, with the lines
orglens find doc <unit> --in notes              # a folder the grammar has no name for
orglens find plan --since 2w                    # touched lately
orglens find article --waiting                  # packets with a gate open, and the question
orglens find spec --grep "x" --json             # path, kind, unit, matches
orglens where [<name>]                          # roots, and which unit a name or this directory is
```

The kind is the grammar's word for where to look; `--in` is the tree's word
where the grammar has none yet. Fire several in one turn rather than scanning.

## Create

```bash
orglens new <path> --kind project [--part-of <unit>] [--home <name>]
```

`new` makes the directory, its marker, a stub driver document (the grammar's
name for it; status line, *What it is*, *State tracking*), and adds the unit to the parent's
`.nav.yml` when that lists children by name. It prints the next steps. The path
given is exactly where it lands; `--home` is repeatable and names another place
the work lives (a code repository). Then write the driver document — `orglens-adapt`
is the skill for shaping one. Documents are written by hand, following the
reference's naming; nothing parses a filename.

```bash
orglens declare <path> [--yes]                  # a folder that exists and looks like a unit but never said so
```

## Launch

```bash
orglens start <unit> [--home <name>] [--prompt "…"]
```

**You can run this.** It launches the agent **detached in tmux** through
`scad session launch`, records the session as this unit's before its first
turn, and returns at once with the way back in: `tmux attach -t <pane>` to
watch, `orglens resume <unit>` to pick it up. `--prompt` is the first turn;
without it the session is told the unit, its homes, and where its status is
written. `--dry-run` prints what would run and the first turn, launches
nothing. Several homes → name one with `--home`. The `[scad] project: …` line
scad prints is scad's own filing by directory; the `attributed … to <unit>`
line after it is orglens's, and both are right.

## Sessions

```bash
orglens sessions <unit>                         # newest first; each says attributed or containment
orglens sessions                                # every unit's, grouped; unattributed last
orglens sessions --none                         # belong to no unit: where they ran, last thing said
orglens resume <unit>                           # its newest open session, through scad
orglens resume <session-id>                     # by id or unique prefix
orglens attribute <session-id> <unit>           # say whose it was, after the fact
```

A session belongs to every unit with a home containing where it ran, or to
the one an attribution names, which wins. A shared home shows the session on
both units; `attribute` narrows it to one. A session started by hand is listed
after scad's next reindex.

## Workflow

```bash
orglens workflow next <packet> --workflow <path>   # bind the packet once, and say what runs
orglens workflow next <packet>                     # node, program, file to write, and the last note
orglens workflow done <packet> --node <n> --agent <who> [--question "…"]
orglens workflow note <packet> "…"                 # answer the open gate
orglens workflow goto <packet> --node <n> --why "…"
```

A capability with state has a `WORKFLOW.yaml`: nodes in a line, each a program
and the one file it writes. `next` derives the position from the packet's
`session.jsonl`; whoever is at the packet performs the program and runs `done`.
A node marked `review: true`, or a `done` with `--question`, waits for `note`.
The tutorial at `capabilities/tutorial/README.md` walks all of it.

## Check

```bash
orglens check                                   # drift: missing driver docs, undeclared folders, weak or shared homes, a unit its parent nav omits, folders the grammar has no word for
orglens view                                    # the page: waiting and running first, then a card per unit; filter by unit, agent, text
orglens config <unit> [--workdir <repo>]        # the repos: block scad reads for a container
orglens reference --out <path>                  # regenerate the grammar reference
```

`check` reports and never gates. Everything it names is a person's one line to
add — a marker, a grammar word, a nav entry — not something to work around.

## Flows

**Start work on a unit:** `where <unit>` → `status | grep <unit>` → `start <unit> --home <name>`.

**Write a plan:** `find plan <unit>` for what exists and the highest number →
write `plans/NN-topic-MonDDYYYY.md` by hand → `snapshot`.

**What needs attention:** `view`, or `sessions --none` and `check`.

**Run one node:** `workflow next` → perform the program, write the one file →
`workflow done` → `workflow next`; waiting means a person runs `note`.

**Pick a unit back up:** `sessions <unit>` → `resume <unit>`.

## Design principle

Never re-derive what you can read. Everything above is derived from the tree,
git, and scad; the only things a person writes are a marker, a grammar line, a
status line, and an attribution. `check` is where the two disagree.
