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

Load organizational topology awareness at session start. The docs tree follows
a strict grammar managed by `orglens`.

## Load Topology

Run at the start of every session to understand what exists:

```bash
orglens snapshot --stdout
```

If `orglens` is not installed or the command fails, skip gracefully.

## Entity Types

The docs tree organizes work into four entity types:

| Type | Location | Key file | Subdirectories |
|------|----------|----------|----------------|
| research-program | `research/` | `research-question.md` | `specs/`, `literature/`, `directions/`, `brainstorms/` |
| experiment | `research/<program>/expt-{n}-{name}/` | `design.md` | `plans/`, `logs/`, `findings/` |
| project | `projects/` | `overview.md` | `specs/`, `plans/`, `logs/` |
| client | `clients/` | `overview.md` | — |

## Artifact Naming

| Type | Directory | Pattern | Example |
|------|-----------|---------|---------|
| plan | `plans/` | `{NN}-{topic}-{MonDDYYYY}.md` | `05-data-collection-Feb062026.md` |
| log | `logs/` | `{NN}-{topic}-{MonDDYYYY}-log.md` | `05-data-collection-Feb062026-log.md` |
| spec | `specs/` | `{topic}.md` | `system-design-v2.md` |

Conventions: kebab-case directories, `{NN}` sequential per-entity (01, 02...), plans and logs form pairs (same number + topic), `{MonDDYYYY}` = three-letter month + day + four-digit year.

## CLI Reference

Always use the CLI for mechanical operations — never construct filenames or scan directories manually.

**Discovery:**

```bash
orglens list                          # all entities
orglens list --type project           # filtered
orglens status                        # status across all entities
orglens find plan                     # all plans
orglens find plan <entity>            # plans scoped to entity
orglens find spec <entity>            # specs scoped to entity
```

**Creation (auto-numbers, auto-dates):**

```bash
orglens new project <name>
orglens new experiment <name> --parent <research-program>
orglens new plan <entity> "<topic>"
orglens new log <entity> "<topic>"
orglens new spec <entity> "<topic>"
```

**Snapshot:**

```bash
orglens snapshot                      # write to cache file
orglens snapshot --stdout             # print to stdout
```

## Design Principle

**Never re-derive what you can read.** Read the snapshot for organizational context. Do not scan directories manually. If the snapshot is stale, run `orglens snapshot` to refresh it.

## Additional Resources

For full grammar specifications, entity type details, status badge conventions, and naming edge cases, consult `references/grammar-reference.md`.
