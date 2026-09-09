---
name: orglens
description: >
  This skill should be used when the user starts a session that involves
  organizational docs, asks "what projects exist", "where do plans go",
  "create a new plan/spec/log", "what's the status of X", or needs to
  understand the organizational topology. Also triggers when the user
  mentions orglens, topology, or organizational structure.
---

# Organizational Context

Load organizational topology awareness at session start. What the tree may
contain is declared in one place — the grammar — and rendered into
`references/grammar-reference.md`. Nothing is restated here, because a second
copy is a copy that drifts.

## Load Topology

Run at the start of every session to understand what exists:

```bash
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
```

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
orglens reference --out <path>        # regenerate the vocabulary reference
```

## Design Principle

**Never re-derive what you can read.** Read the snapshot for organizational
context. Do not scan directories manually. If the snapshot is stale, run
`orglens snapshot` to refresh it.
