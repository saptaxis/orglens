# Capability conventions

A **capability** is a self-contained bundle of programs and skills that moves in
or out of this tree as a unit — one folder per capability, directly under `capabilities/`. This is the shape to copy when adding one.

## What a capability has

- **`README.md`** — the descriptor. What the capability is for, its programs and
  skills, its workflow if it has one, and what triggers it. orglens treats a
  capability as a unit keyed on this file.
- **`WORKFLOW.yaml`** — the capability's workflow, when it has state: an ordered list
  of nodes, each naming a program and the one file it writes. A capability of skills
  alone has none. `orglens workflow` runs it; see the [tutorial](tutorial/README.md).
- **`programs/`** — node programs. One file per program; a program is what one
  node runs, and it is performed by whoever is at the packet: this session, a
  subagent, a container, another model.
- **`skills/`** — `skills/<name>/SKILL.md`, the harness-native form with
  frontmatter, description and triggers. `bootstrap` routes these out.
- **`references/`** — what programs and skills read: templates, a voice, lists
  of patterns. Nothing in it is performed on its own.

## Rules

1. **A program does one pass and writes one file.** Two programs that compose
   beat one that does everything; the workflow is where they are put in order.
2. **A program reads what it says it reads.** Nothing declares reads for it,
   and the engine opens no artifact. A glob that silently matched nothing was
   the previous engine's worst failure, so there is no glob.
3. **State is the packet's session file.** `session.jsonl` records what
   finished, what was asked, and what was answered; position is derived from
   it and never stored. No status flag anywhere to keep in sync.
4. **Programs reach engines through peer skills.** A program gets to Codex,
   Claude or another harness through the invocation layer — a `codex` skill,
   scad, the companion — which handles argv, inputs, sandbox and resume.

## Adding a capability

1. `mkdir <name>/` here, write `README.md`.
2. Put programs under `programs/`, skills under `skills/<name>/`, and whatever
   they read under `references/`. Write `WORKFLOW.yaml` if the programs run in
   order over a packet.
3. Keep domain state (binaries, large outputs) gitignored. Version the
   capability, not the artifacts it produces.
4. `./bootstrap` routes the capability's skills to the harness locations by walking
   the repo for `SKILL.md` files. No central registry to edit.

This repo ships `tutorial`, a three-node workflow for running the engine once.
Working capabilities live in `orglens-extras`, with this same shape.
