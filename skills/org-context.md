---
name: org-context
description: Use at session start to load organizational topology awareness. Reads the orglens snapshot for project structure, conventions, and active state.
---

# Organizational Context

You are working in an environment with an opinionated organizational structure managed by `orglens`. Read the topology snapshot to understand what exists and how things are organized.

## Load Context

Run this at the start of every session:

```bash
orglens snapshot --stdout
```

If `orglens` is not installed or the command fails, skip this step gracefully.

## Organizational Grammar

The docs tree follows a strict grammar:

**Entity types:**
- **research-program** — lives in `research/`. Has `research-question.md`, `research-program-state.md`, subdirs: `specs/`, `literature/`, `directions/`, `brainstorms/`. Contains experiments.
- **experiment** — lives inside a research program as `expt-{n}-{name}/`. Has `design.md`, subdirs: `plans/`, `logs/`, `findings/`.
- **project** — lives in `projects/`. Has `overview.md`, subdirs: `specs/`, `plans/`, `logs/`.
- **client** — lives in `clients/`. Has `overview.md`.

**Artifact naming:**
- Plans: `{NN}-{topic}-{MonDDYYYY}.md` in `plans/` (e.g., `05-data-collection-Feb062026.md`)
- Logs: `{NN}-{topic}-{MonDDYYYY}-log.md` in `logs/` (matching plan numbers)
- Specs: `{topic}.md` in `specs/`

**Conventions:**
- Directories use `kebab-case`
- `{NN}` is sequential per-entity (01, 02, 03...)
- Plans and logs form pairs — same number, same topic
- `{MonDDYYYY}` = three-letter month + day + four-digit year

## When Creating Artifacts

Always use the CLI for mechanical operations:

```bash
# Create a new plan (auto-numbers, auto-dates)
orglens new plan <entity> "<topic>"

# Create a new spec
orglens new spec <entity> "<topic>"

# Create a new log (matching a plan)
orglens new log <entity> "<topic>"

# Scaffold a new project
orglens new project <name>

# Scaffold a new experiment
orglens new experiment <name> --parent <research-program>
```

Never manually construct artifact filenames — let `orglens new` handle numbering and dating.

## When Finding Context

```bash
# What entities exist
orglens list

# What's the current state of everything
orglens status

# Find all plans for an entity
orglens find plan <entity>

# Find all specs
orglens find spec <entity>
```

## Design Principle

**Never re-derive what you can read.** If you need organizational context, read the snapshot. Don't scan directories manually. If the snapshot is stale, run `orglens snapshot` to refresh it.
