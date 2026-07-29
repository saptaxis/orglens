# Deck conventions — the anatomy to copy

A **deck** is a self-contained, themed bundle you can move in or out of the bank freely. This is the pattern to follow when adding one. It was reverse-engineered from `a-private-deck-repo` (the `interior-viz` + `design-book` skills), the first working deck built before the pattern was named.

## What every deck has

- **`DECK.md`** — the descriptor. Purpose, the cards it holds, its state model (if any), and its triggers. This is the deck's `overview.md`; orglens treats a deck as an entity keyed on it.
- **Cards** — one or more of:
  - **operators** (`operators/<name>.md`) — prompted agents, often stateless. The method deck's kind.
  - **skills** (`skills/<name>/SKILL.md`) — harness-native, frontmatter + description + explicit triggers. The domain deck's kind.
  - **agents** (`agents/<name>.md`) — harness-format named agents.
- **packs** (optional, `packs/{bias,voice}/<name>.md`) — the swappable content that parameterizes cards. General skeleton, personal content.

## Three rules the anatomy enforces

1. **Layered, not monolithic.** A deck may compose a base producer with higher-order operators on top — `interior-viz` *generates*, `design-book` *decides between and publishes*. Compose; don't write one skill that does everything.
2. **Spec, not log.** State declares intent; existence is the "done" marker (interior-viz's `plan.yaml` + `versions/vNN.png`). No status flags to keep in sync.
3. **Engines through peer skills, never re-implemented.** A card reaches Codex/Claude/pi through the invocation layer (a `codex` skill's profile, scad, the companion) — it does not reinvent the agent loop. This is scad's companion layer-1: normalize argv/inputs/sandbox/resume in, structured result out.

## Adding a deck

1. `mkdir decks/<name>/`, write `DECK.md`.
2. Drop cards under `operators/` and/or `skills/`; packs under `packs/` if it needs them.
3. Keep domain state (binaries, large outputs) gitignored — version the skills and config, not the artifacts.
4. `bootstrap` discovers the new deck and symlinks its cards to the harness locations. No central registry to edit.

## Method deck vs domain deck

| | Method deck | Domain deck |
|---|---|---|
| Scope | cross-domain (any problem) | one recurring task |
| Cards | mostly stateless operators | skills with domain state |
| Taste lives in | packs (bias/voice) | the skill prompts + state model |
| Example | `method` | `interior-design` |

Both share this anatomy, the orglens grammar, and the bootstrap. That shared pattern — not any single deck's content — is orgdeck's durable asset.
