# Deck conventions

A **deck** is a self-contained, themed bundle of cards that moves in or out of
the bank as a unit. This is the shape to copy when adding one.

## What every deck has

- **`DECK.md`** — the descriptor. Purpose, the cards it holds, its state model (if any), and its triggers. orglens treats a deck as an entity keyed on it.
- **Cards** — one or more of:
  - **operators** (`operators/<name>.md`) — prompted agents, often stateless.
  - **skills** (`skills/<name>/SKILL.md`) — harness-native, with frontmatter, description and explicit triggers.
  - **agents** (`agents/<name>.md`) — harness-format named agents.
- **packs** (optional, `packs/{bias,voice}/<name>.md`) — swappable content that parameterizes cards.

## Rules

1. **Cards compose.** A deck may stack higher-order operators on a base producer: one card generates, another decides between its outputs and publishes. Write two cards that compose rather than one that does everything.
2. **State declares intent; existence is the record.** A plan file says what should be there; the files that exist say what is done. No status flags to keep in sync.
3. **Cards reach engines through peer skills.** A card gets to Codex, Claude or pi through the invocation layer (a `codex` skill's profile, scad, the companion), which normalizes argv, inputs, sandbox and resume in, and hands back a structured result.

## Adding a deck

1. `mkdir decks/<name>/`, write `DECK.md`.
2. Drop cards under `operators/` and/or `skills/`; packs under `packs/` if it needs them.
3. Keep domain state (binaries, large outputs) gitignored. Version the skills and config, not the artifacts.
4. `./bootstrap` routes the new deck's cards to the harness locations by walking the repo for `SKILL.md` files. No central registry to edit.

## Method deck vs domain deck

| | Method deck | Domain deck |
|---|---|---|
| Scope | cross-domain (any problem) | one recurring task |
| Cards | mostly stateless operators | skills with domain state |
| Taste lives in | packs (bias/voice) | the skill prompts + state model |

Both kinds share this anatomy, the orglens grammar and the bootstrap. This repo
ships `tutorial`, a three-node loop for running the engine once. Working decks
of both kinds live in `orglens-extras`.
