---
name: interior-design-book
description: >
  Use when making interior DESIGN DECISIONS across a home/project and assembling them into a
  shareable document — acting as a design partner to walk finishes, doors, edge banding, handles,
  and cabinet interiors unit by unit; reasoning over the whole-project material palette; curating
  options per unit (add/remove/promote); RENDERING units via Codex when a chosen combination has
  no image yet; and building an HTML design book (print → PDF) for an interior execution company.
  Triggers on: "design partner", "help me decide", "go through the decisions", "which finish for
  X", "re-render this in X", "render the kitchen", "add/drop an option", "set the handles", "show
  me the palette", "build the design book".
---

# Interior Design Book — Decide · Render · Publish

**Announce at start:** "I'm using the interior-design-book skill."

Three parts over **one data model** (`design.yaml` + per-unit `plan.yaml`):
1. **Decide** (design partner) — walk the decisions unit by unit (finish, doors, edge banding,
   handles, interiors, layout), recommend, record what the user chooses.
2. **Render** (`render.py` → Codex) — when a chosen combination has no image yet, generate it.
3. **Publish** (`build_book.py`) — assemble decisions + renders + palette into one shareable HTML
   (print → PDF): a highlighted **Selected** per unit, the **Considered** alternatives, all as
   clean metadata tables.

It records *design intent* — not execution drawings (the fitter supplies those). **Codex is a peer
engine reached through `render.py`, not re-implemented here.** `build_book.py` stays pure (no
Codex) so it's fast and deterministic; generation lives only in `render.py`.

## State model

**House `design.yaml`** (at the working root):
```yaml
project: Saptarishi Apartments
brief: "Warm contemporary — wood veneers + stone counters."
palette:                          # whole-house palette, grouped by kind in the book
  - key: teak
    name: Teak veneer
    swatch: materials/teak-veneer.png   # or null for a text-only finish
    kind: veneer                        # floor | veneer | countertop | laminate | tile | hardware (this order in the book)
    status: leading                     # optional: leading/selected → highlighted
    used_in: [flat-4]                   # where it's deployed (for the per-flat Colourway)
areas:                            # rooms/areas + their idea/direction (book order + notes)
  - id: flat-4/kitchen
    idea: "L-shaped modular kitchen; cappuccino / ceramic fronts, beige granite."
```

**Per-unit `plan.yaml`** — a unit holds **builds**. A *build* is one combination; the book
shows its render (or "image not yet rendered") plus its metadata as a table.
```yaml
item: flat-4/kitchen/wall-2
selected: cappuccino-v2           # a build id, or a list of leading builds
builds:
  - id: cappuccino-v2             # → versions/cappuccino-v2.png
    label: Cappuccino — loft removed, corner chimney/stove
    finish: cappuccino            # resolves to a palette material (chip + name)
    doors: grooved                # optional; also auto-derived from id hints
    edge_banding: matt black
    handles: unspecified          # ALWAYS shown; unspecified = still open
    inner_fabric: beige suede     # any extra field renders as a table row
    layout: default               # for layout alternates
    status: considered            # candidate|considered|shortlisted|selected|rejected
  - id: cappuccino
    status: rejected              # kept on disk, hidden from the book
interior:
  spec: "Base: pots drawers + sink cabinet. Uppers: 2 shelves each."
  image: interiors/wall2-inside.png   # optional iPad drawing
progress:                         # readiness tracker → status pills
  finish_finalized: true
  internal_partitions: false
  execution_drawing: false
```

- **`selected`** (build id or list) → featured in the green **Selected** block. Others visible
  → **Considered**. `rejected` → hidden (archived on disk).
- **Any field** on a build renders as a metadata-table row; `handles` always shows
  (`unspecified` until decided). Builds not declared but present as PNGs are auto-added.

## Reference — controlled values

Source of truth: the constants at the top of `build_book.py` (`VISIBLE`, `LEADING`, `KIND_ORDER`,
`DOOR_HINTS`, `RESERVED`). Keep this table in sync if you change them.

**Build `status`** (per build in `plan.yaml`):

| value | in the book |
|-------|-------------|
| `selected`, `leading` | **Selected** block (green spec-sheet) |
| `candidate`, `considered`, `shortlisted` | **Considered** (alternatives) |
| `rejected` | hidden (kept on disk) |
| *(absent)* | `selected` if the id is in the unit's `selected:`, else `considered` |

`--selected-only` keeps only the Selected block.

**Palette material `status`** (per entry in `design.yaml → palette`):

| value | shown as |
|-------|----------|
| `leading`, `selected` | ★ highlighted swatch; included in the per-flat Colourway |
| `todo` | dashed "to be selected" placeholder swatch |
| *(absent)* | plain swatch, no badge |

**Material `kind`** — grouping + order in the palette / colourway:
`floor → veneer → countertop → laminate → tile → hardware` (unknown kinds appended after, alphabetically).

**Door hint tokens** — recognised in a build's `doors:`/`door:`, or inferred from its `id`:
`grooved` (shown "grooved (incised)") · `fluted` · `moulded` ("shaker moulding") · `plaincrockery` ("plain crockery").

**Reserved build fields** — special handling; **any *other* field auto-renders as a metadata row**
(that's how `glass_shutters`, `bathroom_inner_face`, `inner_fabric` just work):
`id`/`v` · `label` · `status` · `finish` · `doors`/`door` · `crockery` · `edge_banding` · `handles` · `inner_fabric` · `layout` · `materials` · `note`/`notes`.

**schematics** — `schematics: {partitions: <img>}` (full-width inside-partitions image, paired with the render), or `schematics: false` to suppress.

## A. Design-partner pass  ← the facilitation flow

Trigger: "let's go through the decisions", "be my design partner", "do a pass on the bedrooms".
Go **area by area, unit by unit** (or a scope the user names). For each unit:

1. **Show where it stands** — its current builds (renders + metadata) and which decisions are
   still `unspecified`/open: finish, doors, edge banding, handles, interior, layout.
2. **Walk one decision at a time.** Present the real options (existing renders, palette
   materials). **Always give a recommendation with reasoning**, then let the user choose. Use
   AskUserQuestion for crisp forks; ask for free text (e.g. a handle) otherwise.
3. **Record immediately** in `plan.yaml`: set `selected`/`status`, fill the metadata field
   (`handles`, `edge_banding`, `inner_fabric`, …), update `progress`.
4. **Render if needed** — if the chosen combination has no image, add the build and make it via
   `render.py` (§D); it slots in as "image not yet rendered" until done.
5. Move on. At the end (or on request) **rebuild the book**.

Keep it conversational and decisive — surface what's undecided, recommend, record. Don't
re-ask settled decisions; don't overwhelm with everything at once.

## B. Curate options (plain-language edits)

| Ask | Action |
|-----|--------|
| "also consider a straighter-grain walnut" | New material → add to palette + `materials/`. Add a build, **render via render.py**, `status: considered`. |
| "drop the plain walnut" | Soft-remove: build `status: rejected` (kept on disk, hidden). Hard-delete only if told. |
| "make walnut-moulded the pick" | Set `selected: walnut-moulded`. |
| "handles = brushed brass on the flat-5 wardrobes" | Set `handles: brushed-brass` on those builds (chip replaces *unspecified*). |
| "try a second layout for wardrobe-2" | Add builds with a different `layout:`, generate. |

## C. Palette & interiors
- Maintain the **palette** in `design.yaml` (name, swatch, kind, used_in, optional `status:
  leading`). It renders grouped by kind, plus a per-flat **Colourway**.
- Per unit fill `interior.spec` and/or drop an `interior.image` (iPad sketch). No generation.

## D. Render an image (render.py → Codex)

`render.py` is a thin, standalone wrapper over the Codex CLI (independent of build_book.py). It
compiles a prompt, calls Codex with the gotchas handled (stdin prompt, `-i` inputs last, sandbox
flags), and harvests the PNG into `versions/<id>.png`.

```bash
python3 skills/interior-design-book/render.py \
  --unit "<root>/<flat>/<room>/<unit>" --out <build-id> \
  --edit versions/<parent>.png     # edit-target(s) to preserve + modify (repeatable) \
  --ref  materials/<swatch>.jpg     # colour / material reference(s) (repeatable) \
  --prompt "<the change>"           # or --prompt @file.txt, or pipe via stdin
```

Idempotent: skips if `versions/<id>.png` exists (use `--force`). `--dry-run` prints the exact
command + assembled prompt; `--examples` prints ready-to-adapt invocations. Input paths resolve
absolute → CWD → the `design.yaml` root (so root-level `materials/x.jpg` works from anywhere).

**Loop:** `render.py` makes the PNG → set `selected:` / add the build in `plan.yaml` →
`build_book.py` publishes. render.py adds the `Asset:` preamble and the `Save as versions/<id>.png`
line, so `--prompt` only needs the change + what to preserve.

**Prompt style — edit-first (change one thing, preserve the rest):**
- **Recolour a finish** (edit = current render, ref = swatch):
  `"Recolour ONLY the cabinet fronts to <colour> matte laminate matching the reference — keep the
  handles, edge banding, counter, layout and everything else identical."`
- **Add a feature** (edit = current render):
  `"Convert ONLY the upper wall cabinets into framed glass shutters — slim <laminate> frame around
  clear glass, <handle> on each. Lower cabinets and everything else unchanged."`
- **Fix a detail** (edit = current render):
  `"Modify ONLY the passage door on the RIGHT: grooved face + aged-brass lever on a rose with a
  keyhole below. Preserve the wardrobe, its handles, the mirror and lighting."`
- **From scratch** (edit = room photo + annotated sketch, ref = material):
  `"Render the wardrobe into the room photo (Image 1) following the annotated sketch (Image 2 —
  spatial guide only, do NOT draw its lines/labels), in the veneer of Image 3. Change only the
  wardrobe region, preserve the rest."`

## E. Build the book
```bash
python3 skills/interior-design-book/build_book.py "<working-root>"   # → <root>/design-book.html
python3 skills/interior-design-book/build_book.py "<working-root>" --selected-only  # selected-only edition
```
Discovers units from the render tree, enriches from `design.yaml` + each `plan.yaml`. Works
before decisions exist (shows all builds); gets richer as they're recorded. Produces one
**self-contained HTML** (images embedded as data-URIs → portable to share; open, Print → PDF):

- **Cover** + brief · **TOC** (navigable) · **Palette** grouped by kind.
- Per flat: a grouped **Colourway** strip.
- Per unit: **✓ Selected** spec-sheet (render + metadata table), **Considered** alternatives
  (grid of render + table), **Interior**, and **Status** pills from `progress`.

The book is a snapshot — **re-run the builder** after changes; new/renamed renders appear then.

## Rules

| Rule | Why |
|------|-----|
| Recommend, then let them choose | It's a design *partner*; surface options + a reasoned pick, don't just execute. |
| Design intent, not execution | Records the user's choices; the fitter provides exact drawings. |
| Soft-remove by default (`rejected`) | Keep provenance — hide, don't delete, unless told. |
| Always surface `unspecified` | Undecided fields (handles, etc.) must be visible, never silently dropped. |
| Generation via render.py → Codex | Codex is a peer engine; build_book.py stays pure (no Codex calls). |
| Rebuild after changes | The HTML embeds images; it only reflects the latest after a rebuild. |
