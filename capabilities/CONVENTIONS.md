# Deck conventions — the anatomy to copy

A **deck** is a self-contained, themed bundle you can move in or out of the bank freely. This is the pattern to follow when adding one. It was reverse-engineered from a single working deck — a domain deck of two composed skills — built before the pattern was named. That is worth stating plainly: the anatomy below has one origin, so treat it as a shape that has worked once, not a law.

## What every deck has

- **`DECK.md`** — the descriptor. Purpose, the cards it holds, its state model (if any), and its triggers. This is the deck's `overview.md`; orglens treats a deck as an entity keyed on it.
- **Cards** — one or more of:
  - **operators** (`operators/<name>.md`) — prompted agents, often stateless. The method deck's kind.
  - **skills** (`skills/<name>/SKILL.md`) — harness-native, frontmatter + description + explicit triggers. The domain deck's kind.
  - **agents** (`agents/<name>.md`) — harness-format named agents.
- **packs** (optional, `packs/{bias,voice}/<name>.md`) — the swappable content that parameterizes cards. General skeleton, personal content.

## Three rules the anatomy enforces

1. **Cards compose.** A deck may stack higher-order operators on a base producer: one card generates, another decides between what it produced and publishes the result. Write two cards that compose rather than one that does everything.
2. **State declares intent; existence is the record.** A plan file says what should be there, and the files that exist say what is done. No status flags to keep in sync.
3. **Cards reach engines through peer skills.** A card gets to Codex, Claude or pi through the invocation layer — a `codex` skill's profile, scad, the companion — which normalizes argv, inputs, sandbox and resume in, and hands back a structured result. The agent loop is somebody else's, already written.

## Adding a deck

1. `mkdir decks/<name>/`, write `DECK.md`.
2. Drop cards under `operators/` and/or `skills/`; packs under `packs/` if it needs them.
3. Keep domain state (binaries, large outputs) gitignored — version the skills and config, not the artifacts.
4. `./bootstrap` routes the new deck's cards to the harness locations, by walking the repo for `SKILL.md` files. No central registry to edit.

## Method deck vs domain deck

| | Method deck | Domain deck |
|---|---|---|
| Scope | cross-domain (any problem) | one recurring task |
| Cards | mostly stateless operators | skills with domain state |
| Taste lives in | packs (bias/voice) | the skill prompts + state model |

This repo ships `tutorial`, which is neither: it exists to be run once and to show that the engine carries no vocabulary of its own. Working decks of both kinds live in `orglens-extras`.

Both kinds share this anatomy, the orglens grammar, and the bootstrap. That shared pattern is the durable asset, rather than any single deck's content.
