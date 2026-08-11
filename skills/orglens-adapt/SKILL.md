---
name: orglens-adapt
description: >
  Bring one entity's driver document into the standard shape, so a person can
  open it and see where that work stands. Use when the user says adapt this
  project, restructure the overview, bring this into the new format, fix up
  this project's status doc, what shape should this overview be, or when
  starting work in an entity whose overview is stale or unstructured. Works on
  one entity at a time and never rewrites prose it did not have to.
---

# Adapt an entity's driver document

One entity per run. You gather evidence, propose the shape, and the human
approves before anything is written.

## Announce

Say: *"Using orglens-adapt to restructure `<entity>`'s driver document."*

## Step 0 — preconditions, both hard

**The entity's files must be committed.** Run `git status --porcelain -- <entity path>`.
If anything is modified, **stop** and say so. Git is the backup — that is the
whole safety model, and it only works if the current version is in it.

**Never write anything outside the driver document.** Not the backlog, not a
spec, not a plan. If content needs to move elsewhere, say where it should go
and let the human move it.

## Step 1 — find the driver document

Ask the grammar. Do not assume a filename — it differs per tree, and the tree
you are in may not be the docs tree.

```bash
orglens reference | head -20        # names the driver document
orglens list --type <kind>          # confirm the entity and its kind
```

## Step 2 — gather evidence

Everything you write must come from something you read. Collect:

```bash
orglens status                      # derived facts, and the current status line with its age
orglens find plan <entity>          # what work was planned, and the latest
orglens find log <entity>           # what actually ran
orglens find spec <entity>          # what was designed
orglens find doc <entity>           # backlogs, handoffs, notes at the root
orglens check                       # anything drifted
git log --oneline -12 -- <path>     # what has actually been happening
```

Then read the existing driver document, the backlog if there is one, and the
most recent handoff or log. Those carry the intent you are reorganising.

## Step 3 — draft the shape

Six sections, in this order, nothing else:

```markdown
# Overview

> **Status:** one sentence, present tense, what is true now

## What it is
Two to four sentences. Stable.

## Where it stands
A short paragraph. What just landed, what is in flight, what it waits on.

## Next
Sorted list, highest first. One line each.

## Open
Questions with no answer yet.

## Elsewhere
Pointers — backlog, map, repo, anything holding detail.
```

Write the draft to a scratch path **outside the tree** and show it as a diff
against the current file. Nothing is written in place yet.

## Step 4 — the four rules

**Restructure, do not rewrite.** Existing prose that works gets *moved*, not
regenerated. "What it is" is usually already written and usually fine. You are
reorganising, not authoring.

**Show what you are removing, before removing it.** Three things come out —
tables of tasks with statuses, counts and measurements, inventories of files.
Some of those rows are real intent that belongs in `Next`. List every removal
explicitly and let the human rescue what matters. This is the only step where
information can be lost.

**Never assert a status the evidence does not support.** If the last commit was
five months ago and no log follows the latest plan, the honest sentence is
*"dormant since March; plan 04 written, never executed"* — not a confident
paragraph reconstructed from filenames. Dormant is a real answer and a useful
one.

**The human sorts `Next`.** Propose an order from what is in flight and what is
blocked, and say it is a proposal. Position is priority, and priority is not
yours to decide.

## Step 5 — write, on approval only

Write the driver document in place. Then:

- Show `git diff` for that one file.
- Say what was removed and where it went, if anywhere.
- Do not commit. The human commits.

## What never goes in

- **Tables of tasks with statuses** — the thing that rots. Intent goes in `Next`, ordered.
- **Counts and measurements** — test totals, file counts. Derived, stale the moment they are typed.
- **Inventories** — lists of specs, plans, documents. The tree holds those already.

Everything else in an authored overview ages fine. These three are the whole
problem, so removing them is most of the job.

## When the list is too long

If `Next` runs past roughly ten items the file stops being readable, which is
the property being protected. Then it splits: the top few stay, the tail moves
to a separate open-work document, and `Elsewhere` points at it.

Propose the cut; do not perform it. Moving content to a second file is outside
this skill's remit.
