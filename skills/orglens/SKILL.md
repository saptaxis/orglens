---
name: orglens
description: >
  Use when a session touches the documents tree or a unit of work: "what
  projects exist", "where does this plan go", "what is the status of X",
  "create a plan/spec/log for X", "which sessions belong to X", "resume the
  last session on X", "start a session on X", "run the next node", "what is
  waiting on me". Also on the words orglens, unit, home, packet, workflow,
  snapshot. Not for a code-only session inside one repository, and not
  inside a container mid-implementation.
---

# Organizational Context

Announce: "Using orglens to <what>."

Load organizational topology awareness at session start. What the tree may
contain is declared in one place — the grammar — and rendered into
`references/grammar-reference.md`. Nothing is restated here, because a second
copy is a copy that drifts.

<HARD-GATE>
Never `ls`, `find`, `glob` or `tree` the documents tree to discover units,
homes, plans, specs or logs. `orglens list`, `orglens find` and the snapshot
already answer that, and a scan answers it wrongly: it sees folders, not
declarations, and a folder is not a unit until a marker says so. Read what the
tool derives. A document's *contents* you read directly, once you know its
path.
</HARD-GATE>

## When not to use this

- A session that only edits code inside one repository and never asks where
  the work is filed.
- A container running one node of a workflow: the packet and the program are
  already in hand, and the sweep may not see the roots.
- Writing prose. That is the writing capability's job; this skill only says
  where the file goes.

## Load Topology

Run at the start of every session to understand what exists:

```bash
orglens snapshot --check || orglens snapshot
orglens snapshot --stdout
```

If `orglens` is not installed or the command fails, skip gracefully.

## What may exist, and what each part is for

Read `references/grammar-reference.md`. It is generated from the grammar by
`orglens reference`, so it cannot disagree with the engine.

Two things it will not tell you, by design:

- **What is actually there.** The grammar describes purpose; only the tree
  knows contents. Entities routinely hold directories nobody declared. The
  snapshot lists them — read it rather than assuming.
- **That anything is required.** A directory that matches a pattern is an
  entity whether or not it holds what the grammar describes. Nothing is hidden
  for being incomplete.

## CLI Reference

Use the CLI to discover. Never scan directories to find out what exists.

**Discovery:**

```bash
orglens list                          # everything in the tree
orglens list --type project           # filtered by kind
orglens status                        # where everything stands
orglens find plan                     # documents of a kind
orglens find plan <unit>              # scoped to just that unit — a nested
                                       # unit's own home is excluded, not included
orglens find spec <unit> --grep "text" # the specs that mention it, with the lines
orglens find doc <unit> --in notes     # a folder the grammar has no name for
orglens find plan --since 2w           # touched in the last two weeks
orglens find article --waiting         # packets with a gate open, and the question
orglens find spec --grep "x" --json    # path, kind, unit, matches — for programs
```

`find` is how you search. The kind says where to look, from the grammar;
`--in` says where to look when the grammar has no word for a folder; `--grep`
reads what was found. Fire several in one turn rather than scanning: `find
spec --grep` and `find doc --in specs2 --grep` together cover a tree whose
grammar has not caught up with it.

**Creation:**

```bash
orglens new <path> --kind project
orglens new <path> --kind experiment --part-of <unit>
orglens declare <path>                # name an existing directory as a unit
orglens declare <path> --yes          # write it without asking
```

`new` creates a unit: a directory, and the declaration that names it. The
path given is exactly where it lands — nothing is numbered for you.
**Write documents yourself**, following the naming description in the
reference. Nothing parses a filename, so a name that departs from the
convention is still found; the convention is for humans reading a directory
listing.

`declare` is for a directory that already exists and looks like a unit but
never said so. It proposes `kind`, `part_of` and a home from what the
directory looks like, shows the reasoning behind each guess, and asks —
position is a good suggestion and a bad fact, so only a person turns one into
the other.

**Attribution:**

```bash
orglens start <unit>                  # attributed before the session's first turn
orglens start <unit> --home <name>    # choose a home when several resolve
orglens start <unit> --dry-run        # name the home and launch nothing
```

Reach for `start` whenever a session is about to begin on a named unit,
instead of launching directly and hoping containment sorts it out later.
Containment answers for work done *inside* a home; it has no answer for work
done *above* one, which is most of what happens at a documents repository
root with many homes underneath it. `start` records the unit first, launches
through scad, and appends one `attributed` event — so the session is joined
to its unit by record, not by guessing from where it landed. If the unit
named is not declared yet, `start` offers to declare it inline, the same way
`declare` does on its own.

**Sessions:**

```bash
orglens sessions <unit>               # the unit's sessions, newest first, with how each is its
orglens sessions                      # every unit's, grouped; unattributed last
orglens sessions --none               # only the sessions belonging to no unit
orglens resume <unit>                 # resume the unit's newest open session
orglens resume <session-id>           # resume one by id or unique prefix
orglens attribute <session-id> <unit> # say which unit a session was for, after the fact
```

A session belongs to a set of units: the one an attribution names, or every
unit with a home containing where it ran. `sessions` shows `attributed` or
`containment` beside each so a session in a shared home reads as intended;
`attribute` narrows such a session to one unit. `resume` hands the id to
`scad session resume`, which knows where the session ran. Use `sessions
--none` as the worklist for what `start` was not used for.

**Workflow:**

```bash
orglens workflow next <packet> --workflow <path>   # bind a packet, and say what runs next
orglens workflow next <packet>                     # node, program, file to write, and any note
orglens workflow done <packet> --node <n> --agent <who> [--question "..."]
orglens workflow note <packet> "..."               # answer the open gate
orglens workflow goto <packet> --node <n> --why "..."
```

A capability with state has a `WORKFLOW.yaml`: nodes in a line, each naming a
program and the one file it writes. `next` derives the position from the
packet's `session.jsonl` and names the program to perform; whoever is at the
packet performs it and runs `done`. A node marked `review: true`, or a `done`
carrying `--question`, waits for a `note` before the next node. The tutorial
at `capabilities/tutorial/README.md` walks all of it in five minutes.

**Container:**

```bash
orglens config <unit>                 # render homes into the config scad reads
orglens config <unit> --workdir <repo>
```

The config a container launcher reads needs a `repos:` block naming the same
homes a unit already declares; `config` renders one instead of it being kept
by hand twice. This is the single place anything here writes a file scad
reads — every other command in this tree only reads scad's own records.
Relevant to the container lane only: launching on this machine with `start`
needs no config at all.

**Audit:**

```bash
orglens check                         # where the tree has drifted
```

Reports only. Nothing is blocked or hidden by what it finds, and it always
exits 0. Run it when tidying, not before working.

**Snapshot:**

```bash
orglens snapshot                      # write to cache file
orglens snapshot --stdout             # print to stdout
orglens snapshot --check              # stale or fresh; exit 1 when stale
orglens reference --out <path>        # regenerate the vocabulary reference
```

## Flows

Commands compose into a few sequences that come up every week.

**Start work on a unit.**

```bash
orglens where <unit>                  # its homes, and which are clean
orglens status | grep <unit>          # what it holds and when it was touched
orglens start <unit> --home <name>    # attributed before the first turn
```

**Write a plan.** The grammar reference says where plans live and how they are
named; nothing numbers or creates the file for you.

```bash
orglens find plan <unit>              # what exists, and the highest number
# write plans/NN-topic-MonDDYYYY.md by hand, following the reference
orglens snapshot                      # so the next session sees it
```

**Check what needs attention.**

```bash
orglens view                          # everything waiting, oldest first
orglens sessions --none               # sessions nobody claimed
orglens check                         # drift, weak or shared homes, folders with no kind
```

**Run one node of a workflow.** The packet is a directory; the workflow is its
capability's `WORKFLOW.yaml`.

```bash
orglens workflow next <packet>        # node, program, file to write, note
# perform the program; write the one file
orglens workflow done <packet> --node <n> --agent <who>
orglens workflow next <packet>        # waiting? then a human runs `note`
```

**Pick up where a unit was left.**

```bash
orglens sessions <unit>               # newest first; open ones say resumable
orglens resume <unit>                 # the newest open one, through scad
```

## Design Principle

**Never re-derive what you can read.** Read the snapshot for organizational
context. Do not scan directories manually. `orglens snapshot --check` says
when it is stale; `orglens snapshot` refreshes it.
