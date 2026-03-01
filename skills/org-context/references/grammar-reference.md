# Grammar Reference

Detailed reference for the orglens organizational grammar. Consult this when
scaffolding entities, validating structure, or understanding naming edge cases.

## Entity Type Specifications

### research-program

- **Location:** `research/<name>/`
- **Required files:** `research-question.md`, `research-program-state.md`
- **Directories:** `specs/`, `literature/`, `directions/`, `brainstorms/`
- **State file:** `research-program-state.md` — contains experiment tracking table
- **Children:** experiment (nested as `expt-{n}-{name}/`)

### experiment

- **Location:** `research/<program>/expt-{n}-{name}/` (inside a research program)
- **Required files:** `design.md`
- **Directories:** `plans/`, `logs/`, `findings/`
- **Dir pattern:** `expt-{n}-{name}` where `{n}` is auto-incremented
- **No state file** — status tracked in parent's `research-program-state.md` table

### project

- **Location:** `projects/<name>/`
- **Required files:** `overview.md`
- **Directories:** `specs/`, `plans/`, `logs/`
- **State file:** `overview.md`

### client

- **Location:** `clients/<name>/`
- **Required files:** `overview.md`
- **Directories:** none required
- **State file:** `overview.md`

## Artifact Naming Patterns

### plan

- **Directory:** `plans/`
- **Pattern:** `{NN}-{topic}-{MonDDYYYY}.md`
- **Example:** `05-data-collection-Feb062026.md`
- **`{NN}`:** Zero-padded sequential number per entity (01, 02, 03...)
- **`{topic}`:** Kebab-case topic slug
- **`{MonDDYYYY}`:** Three-letter month + day (no padding) + four-digit year

### log

- **Directory:** `logs/`
- **Pattern:** `{NN}-{topic}-{MonDDYYYY}-log.md`
- **Example:** `05-data-collection-Feb062026-log.md`
- **Logs pair with plans** — same `{NN}` and `{topic}`

### spec

- **Directory:** `specs/`
- **Pattern:** `{topic}.md`
- **Example:** `system-design-v2.md`
- **No numbering or dating** — specs are evergreen documents

## Status Badge Convention

State is extracted from markdown files using a regex pattern. The convention:

```markdown
> **Status:** Active
```

Rules:
- Must use `**Status:**` (bold, with colon)
- First match in the file wins
- Parenthetical suffixes are stripped: `Active (Plan 01 done)` → `active`
- Text after first comma is stripped: `Design complete, impl pending` → `design complete`
- Result is lowercased
- If no `**Status:**` badge exists, status reads as `None`

### Table status extraction

For `research-program-state.md`, status is also extracted from markdown tables
with a "Status" column:

```markdown
| # | Name | Status |
|---|------|--------|
| 1 | Agent Behavior | **Complete** |
| 2 | World Model Study | **Active** |
```

Bold markers in table cells are stripped. Only the first table with a Status column is processed.

## Directory Tree Example

```
docs/
├── research/
│   └── physics-priors/
│       ├── research-question.md
│       ├── research-program-state.md
│       ├── specs/
│       ├── literature/
│       ├── directions/
│       ├── brainstorms/
│       └── expt-1-agent-behavior/
│           ├── design.md
│           ├── plans/
│           │   ├── 01-testbed-Feb032026.md
│           │   └── 02-data-collection-Feb062026.md
│           ├── logs/
│           │   └── 01-testbed-Feb032026-log.md
│           └── findings/
├── projects/
│   ├── clipcompose/
│   │   ├── overview.md
│   │   ├── specs/
│   │   ├── plans/
│   │   └── logs/
│   └── orglens/
│       ├── overview.md
│       ├── specs/
│       ├── plans/
│       └── logs/
└── clients/
    └── freightify/
        └── overview.md
```
