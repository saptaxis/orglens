---
name: interior-viz
description: >
  Use when generating or iterating interior-design visualizations from a room
  photo, an annotated schematic sketch, and material references — wardrobes,
  kitchens, TV units, vanities, counters. Walks house → room → item → regions →
  materials with the user to author a per-item plan.yaml of versions, then
  generates the unbuilt ones via Codex. Triggers on: "visualize this wardrobe",
  "render the kitchen wall", "try walnut on that panel", "add a variant", "run the plan".
---

# Interior Visualization — Sketch + Materials → Render

**Announce at start:** "I'm using the interior-viz skill to plan and generate this visualization."

Generate photorealistic interior visualizations as **conditional edits**: take a real
room photo, an annotated schematic drawn over it, and material references, and render
the proposed built-in unit — changing only the marked regions, preserving everything else.

**The `plan.yaml` is a spec you author, not a log of the past.** You (with the skill's help)
declare the versions you want; on **run**, the skill generates the ones that don't exist yet.
Edit the plan, hit run, repeat.

The actual image call goes through the **codex** skill's `image` profile. This skill owns the
*workflow*: authoring the plan, resolving inputs, compiling prompts, and deciding what to
build. It does **not** re-implement Codex invocation — read the codex skill for CLI details
(stdin/`-i` gotcha, sandbox, harvesting generated files).

## State model

Everything lives under a **working root** — default `work/` in this repo (gitignored, so the
image binaries stay out of git and sync via Dropbox). Confirm the root with the user at the
start (step 1); they may point it elsewhere.

```
<root>/<house>/<room>/<item>/     e.g. work/my-flat/living-room/wardrobe-1/
  base.jpg          clean room/wall photo = edit target (Image 1)
  sketch.png        annotated schematic; regions labelled (countertop, shelf, knob…) = spatial guide (Image 2)
  materials/        palette of material images, named by MATERIAL not region
    teak-veneer.jpg  walnut-veneer.jpg  white-quartz.jpg
  versions/         v01.png v02.png v03.png   ← outputs; existence = "already built"
  plan.yaml         the spec of versions to build
```

- **Materials are named by material, not region.** A region tries this/that by pointing at a
  different file across versions. Region→material mapping lives per-version in `plan.yaml`.
- **No `design.yaml`, no status flags.** The plan declares intent; the presence of
  `versions/vNN.png` is the only "done" marker. Nothing else to keep in sync.

## The plan (`plan.yaml`)

You author it. Each entry declares a version's *intent* only — `v`, `parent`, `change`, `map`.
The skill compiles the codex prompt and resolves inputs at run time; you never hand-write prompts.

```yaml
item: my-flat/living-room/wardrobe-1
versions:
  - v: v01
    parent: base                     # base = the empty photo + sketch; or another vNN
    change: initial finishes
    map:                             # region → material file, or a text description
      countertop: white-quartz.jpg
      lower: teak-veneer.jpg
      panel: teak-veneer.jpg
      knobs: "brushed brass"         # text-only material (no image)

  - v: v03
    parent: v01                      # a variant branches from a built version
    change: panel → walnut
    map: { countertop: white-quartz.jpg, lower: teak-veneer.jpg,
           panel: walnut-veneer.jpg, knobs: "brushed brass" }

  - v: v04
    parent: v01
    change: warm late-afternoon lighting from the left   # a non-material change; map unchanged
    map: { countertop: white-quartz.jpg, lower: teak-veneer.jpg,
           panel: teak-veneer.jpg, knobs: "brushed brass" }
```

A **variant** is a new entry branching from a built `parent`, differing in one `map` line or one
`change`. Never branch a variant from `base` — geometry drifts and comparisons break.

### Run semantics — how the skill decides what to build

On **run**, the skill:

1. Reads `plan.yaml` and lists the declared versions.
2. Orders them by dependency (`parent` before child; `base`-parented first).
3. For each version whose **`versions/vNN.png` does not exist yet**, builds it (a version whose
   parent isn't built yet is built after its parent, same run).
4. **Skips** any version whose PNG already exists — the plan is idempotent; re-running only
   fills in what's missing.

So the workflow is: **author/edit the plan → run → skill builds the new entries.** To **rebuild**
an existing version (e.g. you changed its `map`), delete its `versions/vNN.png` first, or ask to
`run v03` to force just that one. Report what was built and what was skipped.

## Workflow

Work through these with the user. Skip steps already satisfied.

1. **Set the working root, then locate/create the item.** Confirm the working root (default
   `work/`); create it if missing. Establish house → room → item under it; create the folder tree.
2. **Confirm inputs.** Ensure `base.jpg` (edit target) and `sketch.png` (annotated schematic)
   exist. If missing, ask the user to add them or point to them.
3. **Read regions.** **Look at `sketch.png`** (Read the image) to enumerate the annotated regions
   — countertop, shelves, shutters, knobs, panels, niches. Confirm the list with the user.
4. **Author the plan.** With the user, add version entries to `plan.yaml`. For each region in a
   version's `map`:
   - If a matching image exists in `materials/`, use its filename.
   - If not, **ask the user** (AskUserQuestion) for a short description (e.g. "brown teak veneer,
     vertical grain") and record it as a text value in `map`.
   Set `parent` (`base` for a fresh unit, a built `vNN` for a variant) and a one-line `change`.
5. **Run.** Build every declared version with no output PNG, in parent order (see Run semantics).
6. **Review.** Show the built PNGs. The user iterates by editing/adding plan entries and running
   again; a version they like becomes the `parent` of the next variant.

## Building one version

For each version the run decides to build:

**Resolve inputs** from `parent` + `map`:
- `parent: base` → edit target is `base.jpg` (Image 1) + `sketch.png` (Image 2, spatial guide);
  then the image-valued materials in `map`, in region order (Images 3…N).
- `parent: vNN` → edit target is `versions/vNN.png` (Image 1, the parent render); attach only the
  material image(s) that changed for this version (Images 2…N). The sketch is usually unneeded
  once geometry is placed.

**Compile the prompt** from `change` + `map` (short, labelled, explicit):

```
Asset: photorealistic interior visualization. Use your image_generation tool (not code).
Inputs:
- Image 1: EDIT TARGET (base photo, or the parent render). Preserve camera, crop, room, lighting.
- Image 2: annotated schematic — SPATIAL GUIDE ONLY (only on base-parented builds). Never render
  its colours, labels, lines, or dimensions.
- Images …: material references, in region order: <region=material, …>.

Change: <the entry's `change`>, applied via — <region → material image N / "text description">.
Match grain direction and plausible scale; match the room's light, contact shadows, reflections.
Preserve everything else: walls, floor, ceiling, openings, fixed elements, and (when branching) the
parent's geometry and any regions not being changed.
Do not add decor, people, plants, or unrequested objects. Do not show any annotation colours,
labels, arrows, dimensions, or guide lines.
Save the result as versions/vNN.png in the current working directory.
```

**Run the codex call** (codex skill's `image` profile). Key points (details there):

- Pipe the prompt via **stdin**; put `-i` inputs **last** (the `-i` variadic gotcha).
- **`--skip-git-repo-check`** — item folders are not git repos; codex refuses to run without it.
- `-C <item dir>` and `-s workspace-write` so output is predictable.
- **Branching a variant** resumes the parent's thread when known — **ordering gotcha:** with
  `codex exec resume`, exec-level flags (`-C`, `-s`, `--skip-git-repo-check`, `--json`, `-o`) go
  **before** `resume`; only `-i`/`-m`/`-c` attach after the session id. Passing the parent PNG as
  the `-i` edit target also works without resuming.
- **Long timeout or backgrounded.** Gen takes ~1–2 min and the codex process lingers *after* the
  PNG is written. The image lands in `~/.codex/generated_images/<thread_id>/` (and `versions/` if
  you told codex to save there) **even if the wrapper is killed on timeout** — check for the file
  before assuming failure. Harvest the PNG into `versions/vNN.png`.

```bash
# base-parented build
printf '%s' "$PROMPT" | codex exec -C "$ITEM_DIR" --skip-git-repo-check --json -s workspace-write \
  -i base.jpg -i sketch.png -i materials/white-quartz.jpg -i materials/teak-veneer.jpg

# variant branched from v01 (edit target = parent render)
printf '%s' "$PROMPT" | codex exec -C "$ITEM_DIR" --skip-git-repo-check --json -s workspace-write \
  -i versions/v01.png -i materials/walnut-veneer.jpg
```

## Staged pipeline (optional, for complex units)

For a hard unit, plan the stages as chained versions instead of one shot — each `parent`ed on the
previous, approved by eye before you plan the next:

1. **Geometry** — neutral matte grey; judge placement, scale, perspective, bay divisions only.
2. **Finishes** — parented on geometry; apply the mapped materials.
3. **Details** — handles, grooves, edge profiles, glass, lighting; one change per version.
4. **Variants** — branch alternatives from the same finished parent, one change each.

## Rules

| Rule | Why |
|------|-----|
| `plan.yaml` is a spec, not a log | You author intended versions; run builds the missing ones. Don't treat it as a record of the past. |
| One targeted change per version | Multiple simultaneous changes make comparison and blame impossible. |
| Existence of `versions/vNN.png` = built | The only "done" marker. Rebuild by deleting the PNG or forcing `run vNN`. No status flags. |
| Branch variants from a built version, never from `base` | Regenerating from scratch drifts geometry; comparisons become unreliable. |
| Never overwrite `base.jpg`, `sketch.png`, or an existing version PNG | Originals and built outputs are immutable; new work is a new version. |
| Missing material image → ask the user for text, don't invent | The user owns the material choice; record what they said in `map`. |
| Generated colour is approximate | Not a procurement authority; final material choice is from physical samples. |
