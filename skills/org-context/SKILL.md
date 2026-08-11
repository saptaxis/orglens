---
name: org-context
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
orglens find plan <entity>            # scoped to an entity and its children
```

**Creation:**

```bash
orglens new project <name>
orglens new experiment <full-name> --parent <entity>
```

`new` creates entities only, and the name is given in full — nothing is
numbered for you. **Write documents yourself**, following the naming
description in the reference. Nothing parses a filename, so a name that
departs from the convention is still found; the convention is for humans
reading a directory listing.

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
