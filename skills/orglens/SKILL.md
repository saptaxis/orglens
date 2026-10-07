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
orglens snapshot --stdout --unit <name>         # one unit and everything under it in the tree
orglens snapshot --json [--unit <name>]         # the same facts as data, to compose with
```

The snapshot is the tree as one document. `--type`/`--unit` narrow it; the
unscoped one is 500+ lines. The grammar's own words for what may exist are in
`references/grammar-reference.md`, generated, never restated here.

## Find

```bash
orglens list [--type KIND]                      # units by organisation and branch kind, newest first
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
`orglens tree [<unit>]` shows the units as a tree; `--under <unit>` on `list`,
`status` and `find` keeps one unit and everything under it.

A closing `N hidden` line means the person keeps units off the screen
(`orglens hide`). Leave the hide as it is; `--show-hidden`, `--json` or naming
the unit shows them to you.

## Create

```bash
orglens new <path> --kind project [--part-of <unit>] [--home <name>]
```

`new` makes the directory, its marker, a stub driver document (the grammar's
name for it, in the grammar's format; status line, *What it is*, *State tracking*), every other file the kind's `structure:` declares (seeded with a title and what it is for), and adds the unit to the parent's
`.nav.yml` when that lists children by name. It prints the next steps. The path
given is exactly where it lands; `--home` is repeatable and names another place
the work lives (a code repository). Then write the driver document — `orglens-adapt`
is the skill for shaping one. Documents are written by hand, following the
reference's naming; nothing parses a filename.

**A parent is the person's to state.** `part_of` puts a unit in the tree, and
where the folder sits does not. Never pass `--part-of` from position alone: when
the folder sits inside a unit, ask the person whether it is part of that unit,
naming it, and pass `--part-of` only on a yes. Run without a terminal, `new` and
`declare` write no parent they were not given.

A tree may hold markdown and org side by side, and both are read. Write a new
document in the grammar's `format` (the reference says which); keep an existing
one in the format it is in. The status line is `#+STATUS: …` under `#+TITLE:` in
org, `> **Status:** …` in markdown. `check` reports a document written in both.

```bash
orglens declare <path> [--yes] [--part-of <unit>]  # a folder that exists and looks like a unit but never said so
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

`--window` lands it as a window in the tmux you are already in instead of a
detached one, so the person can switch to it rather than attach. The session is
named `<unit>-<mon><dd>`; `--about "two words"` puts context in the middle,
which is what tells two sessions on one unit on one day apart. Both need a scad
that has `session launch --window`. `--split` lands it in a pane beside the
one you are in instead.

## Sessions

```bash
orglens sessions <unit>                         # newest first; each says attributed or containment
orglens sessions                                # every unit's, grouped; unattributed last
orglens sessions --none                         # belong to no unit: where they ran, last thing said
orglens resume <unit>                           # its newest session, running first, through scad
orglens resume <unit> <name>                    # the unit's session of that name (TAB lists them)
orglens resume <session-id>                     # by id or unique prefix
orglens attribute <session-id> <unit> --why "…" # say whose it was, and what for
orglens resume <unit> --prompt "…"              # hand a turn to the open session
orglens memos <unit>                            # what was written down about it (scad's memos)
orglens sessions --none --groups                # the unclaimed, counted by directory
```

A session belongs to every unit with a home containing where it ran, or to
the one an attribution names, which wins. A shared home shows the session on
both units; `attribute` narrows it to one. A session started by hand is listed
after scad's next reindex. When `sessions`, `resume` or `status` says the index
is old, run `scad reindex` before trusting what they list; `view` does it itself.

`--why` is the person's own words about a session and is shown wherever it is
listed; ask for it rather than inventing one. `resume --prompt` delivers a turn
to a pane that is already open, which is not the same as resuming — and `resume`
names any other live process on that session id before opening it, because two
writers on one transcript is how a session forks.

`orglens memos <unit>` says why each memo is the unit's: `written here` (the
session that wrote it belongs to the unit), `filed here` (scad's project for
it), or `mentions this` (the name appears in it). `--no-mentions` drops the
weakest, `--kind` is not there yet.

**Clearing the unclaimed pile is the person's, not yours.** `sessions --triage`
walks it by directory and takes a unit name, `d` to dismiss, `s` to skip. It is
interactive and it never proposes a unit, because a session above every home
could be any of the units under it. Offer it; do not run it.

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
orglens check                                   # drift: missing driver docs, undeclared folders, homes under no root, part_of naming no unit or a cycle, a folder disagreeing with its marker, weak or shared homes, a unit its parent nav omits, folders the grammar has no word for, a document in two formats
orglens view                                    # the page: Recent (cards banded by time) and Explore (the tree); filter by scope, kind, agent, text
orglens config <unit> [--workdir <repo>]        # the repos: block scad reads for a container
orglens reference --out <path>                  # regenerate the grammar reference
```

`check` reports and never gates. Everything it names is a person's one line to
add — a marker, a grammar word, a nav entry — not something to work around.

## Flows

**Start work on a unit:** `where <unit>` → `status | grep <unit>` → `start <unit> --home <name>`.

**Write a plan:** `find plan <unit>` for what exists and the highest number →
write `plans/NN-topic-MonDDYYYY` in the grammar's format (`.org` or `.md`) by hand → `snapshot`.

**What needs attention:** `view`, or `sessions --none` and `check`.

**Run one node:** `workflow next` → perform the program, write the one file →
`workflow done` → `workflow next`; waiting means a person runs `note`.

**Pick a unit back up:** `sessions <unit>` → `resume <unit>`.

## Design principle

Never re-derive what you can read. Everything above is derived from the tree,
git, and scad; the only things a person writes are a marker, a grammar line, a
status line, and an attribution. `check` is where the two disagree.
