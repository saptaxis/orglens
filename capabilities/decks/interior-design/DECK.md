# interior-design — deck descriptor

> Kind: **domain deck** (one recurring real task). Status: **ported 2026-07-28** from
> `~/Dropbox/code/a-private-deck-repo` — Phase 1, as-is. Root handling unchanged.

Photorealistic interior-design visualization as *conditional edits*: a room photo + an annotated
schematic sketch + material references → a rendered built-in unit, changing only the marked
regions. A design-decision and document-building workflow sits on top.

This was the first deck — built before the pattern was named, and reverse-engineered into
[`CONVENTIONS.md`](../../CONVENTIONS.md).

## Cards

| Card | Role |
|---|---|
| `skills/interior-viz/SKILL.md` | **The producer.** Walks house → room → item → regions → materials with the user, authors a per-item `plan.yaml` of wanted versions, then generates the unbuilt ones. Reaches image generation through a peer `codex` skill — it does not re-implement the agent loop. |
| `skills/interior-design-book/SKILL.md` | **The higher-order operator.** Sits on top of the producer: design-partner facilitation, curating options per unit, reasoning over the whole-project palette, re-rendering when a chosen combination has no image, and assembling a self-contained HTML design book (print → PDF). |
| `skills/interior-design-book/build_book.py` | The HTML assembler. Takes the working root as `argv[1]`. |
| `skills/interior-design-book/render.py` | Render driver. |

Both `SKILL.md` files are Agent Skills spec-compliant (`name` matches the parent directory).

## State model

**Spec, not log.** A per-item `plan.yaml` *declares* the versions wanted; the existence of
`versions/<id>.png` is the only "done" marker. There is no status flag to keep in sync.

Domain state — `work/`, `versions/`, image binaries — is **gitignored**. Real project roots (e.g.
a specific apartment's `interior-visualization/` folder) live outside this tree and sync via
Dropbox. The deck is versioned; the artifacts are not.

## Dependencies

- **PyYAML** and **Pillow** — imported lazily by `build_book.py` (lines 20, 24), so it fails with a
  clear message rather than at import time.
- **scad's `codex` skill** (`scoped-agent-dispatch/skills/codex/SKILL.md`, `image` profile) — load
  scad's plugin when smoke-testing, or generation will not resolve.

## Root handling — deliberately unchanged

`build_book.py` takes its root as `argv[1]` (tier 1); `interior-viz` carries a prose default of
`work/` (tier 0). **Both were left exactly as they were during this port.** Swapping them for
scad's `resolve()` (`marker=design.yaml`, target = the apartment dir) is the next step and is now
unblocked — scad's resolver engine shipped 2026-07-28 (plan 17). Kept separate so the port and the
refactor stay independently reviewable.

Background on the pattern: `~/Desktop/working-root-vs-passing-paths.md`.

## Not ported

- `work/` — 6.4M of gitignored test state.
- `examples/saptarishi/` — 4.1M of tracked config for real flats. **Open decision:** bring in as
  reference, leave in the source repo, or treat as working-root data outside the deck.
- `.claude-plugin/plugin.json` — the source was a standalone plugin; distribution is the bootstrap's
  job here.
- `CONDITIONAL_IMAGE_GENERATION*.md` design notes — **open decision** whether they follow.
