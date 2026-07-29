#!/usr/bin/env python3
"""render.py — generate / re-render a single interior visualization via the Codex CLI.

Standalone helper for the interior-design-book workflow. Wraps `codex exec` with the gotchas
baked in (prompt via stdin, `-i` inputs last, sandbox flags, and harvesting the PNG that
lands even after codex lingers past the write). Independent of build_book.py — no
design.yaml, no schema, no coupling.

The loop:
  1. render.py  → produces  <unit>/versions/<id>.png
  2. edit plan.yaml: point `selected:` at <id> (or add a build with that id)
  3. build_book.py <root>  → publishes the book

Usage:
  render.py --unit <unit-dir> --out <id> --prompt "<change>" \
            [--edit <img> ...] [--ref <img> ...] [--force] [--dry-run] [--timeout 320]

  # prompt from a file, or stdin:
  render.py --unit <dir> --out <id> --prompt @change.txt
  echo "<change>" | render.py --unit <dir> --out <id>

  render.py --examples        # print example invocations

Inputs (`--edit`, `--ref`) resolve as absolute, else relative to CWD, else relative to
--unit — so root-level `materials/x.jpg` and unit-level `versions/parent.png` both work.
`--edit` images are the EDIT TARGET(s) to preserve + modify; `--ref` images are colour /
material references. render.py adds a standard preamble and the `Save as versions/<id>.png`
line, so your --prompt only needs to describe the change.
"""
import sys, os, argparse, subprocess, glob, shutil, time

PREAMBLE = "Asset: photorealistic interior visualization. Use your image_generation tool (not code)."
GEN_DIR = os.path.expanduser("~/.codex/generated_images")

EXAMPLES = r"""
# Recolour only the cabinet fronts (edit target = the current render, ref = a swatch photo):
render.py --unit flat-5/kitchen/wall-2 --out 22107-glass \
  --edit versions/22107-band-black.png --ref materials/22107_sample.jpg \
  --prompt "Recolour ONLY the cabinet fronts to a light warm greige (British Buff) matte laminate
matching the reference colour — clearly lighter and greyer than cream. Keep the matte-black pulls,
matte-black edge banding, black granite, layout and everything else identical."

# Add a feature to one region (no reference image needed — colour is already in the target):
render.py --unit flat-4/kitchen/wall-2 --out cappuccino-glass \
  --edit versions/cappuccino-v2-knobs.png \
  --prompt "Convert ONLY the upper (above-counter) wall cabinet doors into framed GLASS SHUTTERS:
a slim cappuccino-laminate frame around a clear glass panel, aged-brass knob on each. Lower cabinets
stay solid cappuccino. Change nothing else."

# Fix one detail (grooves + handle) on a passage door in an existing render:
render.py --unit flat-4/bedroom-3/wardrobe-1 --out teak-reeded-doorfix \
  --edit versions/teak-reeded.png --ref materials/teak-veneer.png \
  --prompt "Modify ONLY the passage door on the RIGHT: give it a grooved teak face and an aged-brass
lever on a round rose with a separate keyhole below. Preserve the wardrobe, its knobs, the mirror,
walls, floor and lighting."

# Fresh render from a room photo + annotated sketch + materials (the from-scratch case):
render.py --unit flat-4/bedroom-3/wardrobe-1 --out teak \
  --edit base.png --edit sketch.png --ref materials/teak-veneer.png \
  --prompt "Render the built-in wardrobe into the room photo (Image 1) following the annotated
schematic (Image 2 — spatial guide only; do NOT render its lines, labels or colours), finished in the
teak veneer (Image 3). Match the room's lighting, perspective and contact shadows; change only the
wardrobe region, preserve everything else."
""".strip("\n")


def find_root(unit):
    """Nearest ancestor of the unit containing design.yaml (the working root)."""
    d = os.path.abspath(unit)
    for _ in range(8):
        if os.path.exists(os.path.join(d, "design.yaml")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def resolve(path, unit, root):
    cands = [path, os.path.join(unit, path)] + ([os.path.join(root, path)] if root else [])
    for cand in cands:
        if os.path.exists(cand):
            return os.path.abspath(cand)
    sys.exit(f"render.py: input not found: {path} (looked in CWD, {unit}"
             + (f", and root {root})" if root else ")"))


def main():
    if "--examples" in sys.argv:
        print(EXAMPLES); return
    ap = argparse.ArgumentParser(description="Render one interior-viz image via Codex.")
    ap.add_argument("--unit", required=True, help="unit dir; output goes to <unit>/versions/<id>.png")
    ap.add_argument("--out", required=True, help="output build id (versions/<id>.png)")
    ap.add_argument("--prompt", help="change description; text, @file, or omit to read stdin")
    ap.add_argument("--edit", action="append", default=[], help="edit-target image(s) to preserve+modify (repeatable)")
    ap.add_argument("--ref", action="append", default=[], help="material/colour reference image(s) (repeatable)")
    ap.add_argument("--force", action="store_true", help="re-render even if versions/<id>.png exists")
    ap.add_argument("--dry-run", action="store_true", help="print the codex command + prompt, don't run")
    ap.add_argument("--timeout", type=int, default=320, help="seconds (codex lingers; the PNG lands anyway)")
    ap.add_argument("--model", help="optional codex model override")
    a = ap.parse_args()

    unit = os.path.abspath(a.unit)
    if not os.path.isdir(unit):
        sys.exit(f"render.py: --unit not a directory: {unit}")
    out_png = os.path.join(unit, "versions", a.out + ".png")
    if os.path.exists(out_png) and not a.force:
        sys.exit(f"render.py: {out_png} already exists — use --force to re-render.")

    # prompt: --prompt text / @file / stdin
    p = a.prompt
    if p and p.startswith("@"):
        p = open(p[1:]).read()
    elif not p:
        p = sys.stdin.read()
    if not p.strip():
        sys.exit("render.py: empty prompt (pass --prompt or pipe via stdin).")

    root = find_root(unit)
    inputs = [resolve(x, unit, root) for x in a.edit] + [resolve(x, unit, root) for x in a.ref]
    hint = ""
    if inputs:
        n = len(a.edit)
        hint = (f"\nInputs: the first {n} image(s) are the EDIT TARGET — preserve them and apply only the "
                f"described change; any remaining images are colour / material references." if n else
                "\nInputs: the provided images are colour / material references.")
    full = f"{PREAMBLE}{hint}\n\n{p.strip()}\n\nSave the result as versions/{a.out}.png in the current working directory."

    os.makedirs(os.path.join(unit, "versions"), exist_ok=True)
    log = os.path.join(unit, "versions", f".{a.out}.codex.log")
    cmd = ["codex", "exec", "-C", unit, "--skip-git-repo-check", "--json", "-s", "workspace-write", "-o", log]
    if a.model:
        cmd += ["-m", a.model]
    for i in inputs:
        cmd += ["-i", i]

    if a.dry_run:
        print("COMMAND:\n  " + " ".join(cmd) + "\n\nPROMPT (via stdin):\n" + full)
        return

    start = time.time()
    try:
        subprocess.run(cmd, input=full, text=True, timeout=a.timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        pass  # codex often lingers past the write; the PNG still lands — check below.

    if not os.path.exists(out_png):
        # fallback: harvest the newest PNG codex generated during this run
        cands = [f for f in glob.glob(os.path.join(GEN_DIR, "**", "*.png"), recursive=True)
                 if os.path.getmtime(f) >= start - 2]
        if cands:
            shutil.copy(max(cands, key=os.path.getmtime), out_png)

    if os.path.exists(out_png):
        print(f"OK  {out_png}")
    else:
        sys.exit(f"render.py: no output produced. Check the log: {log}")


if __name__ == "__main__":
    main()
