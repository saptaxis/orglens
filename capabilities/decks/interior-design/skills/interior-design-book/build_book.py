#!/usr/bin/env python3
"""Assemble the interior design book (self-contained HTML → print to PDF).

Usage:  python3 build_book.py <working-root> [output.html] [--selected-only]

--selected-only: emit a clean edition with ONLY the chosen build per unit — no
"Considered" alternatives, palette trimmed to selected/leading/todo materials.
Defaults its output to design-book-selected.html so the full book is untouched.

BUILD-DRIVEN: each unit declares 'builds' in its plan.yaml — a build is one
combination (finish + doors + edge banding + handles + inner fabric + layout …).
Per unit the book shows a highlighted SELECTED spec-sheet (what to execute) and a
CONSIDERED section (alternatives, for the execution company's input). Each build's
metadata renders as a table; the render shows if it exists, else "image not yet
rendered". Builds are auto-derived from versions/*.png when none are declared.
"""
import sys, os, glob, base64, io, html, re

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")
try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow required: pip install pillow")

SELECTED_ONLY = False   # set from --selected-only: drop 'Considered' sections, keep full palette
VISIBLE = {"candidate", "considered", "shortlisted", "selected", "leading"}  # 'rejected' hidden
LEADING = {"leading", "selected"}
KIND_ORDER = ["floor", "veneer", "countertop", "laminate", "tile", "hardware"]
DOOR_HINTS = {"grooved": "grooved", "fluted": "fluted", "moulded": "shaker moulding",
              "plaincrockery": "plain crockery"}
FIELD_LABELS = {"edge_banding": "Edge banding", "handles": "Handles",
                "inner_fabric": "Inner fabric", "layout": "Layout"}
RESERVED = {"id", "v", "status", "label", "note", "notes", "materials", "finish",
            "door", "doors", "crockery", "handles", "edge_banding", "inner_fabric", "layout"}


def data_uri(path, max_edge=1000, quality=82):
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        return None
    w, h = im.size
    if max(w, h) > max_edge:
        s = max_edge / max(w, h)
        im = im.resize((max(1, int(w * s)), max(1, int(h * s))))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def load_yaml(path):
    if os.path.exists(path):
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def prettify(s):
    return str(s).replace("-", " ").replace("_", " ")


def render_brief(brief):
    lines = [l.strip() for l in brief.splitlines() if l.strip()]
    out = []
    for l in lines:
        if l.lower().startswith("flat-") and "—" in l:
            k, rest = l.split("—", 1)
            out.append(f'<div class="fline"><b>{esc(k.strip())}</b> — {esc(rest.strip())}</div>')
        else:
            out.append(f'<div class="fintro">{esc(l)}</div>')
    return '<div class="brief">' + "".join(out) + '</div>'


def slug(*parts):
    return re.sub(r"[^a-z0-9]+", "-", "-".join(parts).lower()).strip("-")


def used_here(item, flat):
    return any(u == flat or u.startswith(flat + "/") for u in (item.get("used_in") or []))


def room_key(room):
    return (0 if room == "doors" else 1, room)   # fallback: doors first per flat


def ordered_rooms(flat, rooms, area_order):
    """Room order follows design.yaml `areas` order for this flat; unlisted rooms fall to the end."""
    idx = {}
    for i, aid in enumerate(area_order):
        parts = aid.split("/", 1)
        if len(parts) == 2 and parts[0] == flat and parts[1] not in idx:
            idx[parts[1]] = i
    return sorted(rooms, key=lambda r: (idx.get(r, 10000), room_key(r)))


def match_material(token, palette):
    for m in palette:
        key, sw = m.get("key", ""), os.path.basename(m.get("swatch") or "")
        if token == key or (len(token) > 2 and (token in key or key in token or token in sw)):
            return m
    return None


def mat_inline(root, val, palette):
    m = match_material(str(val), palette)
    if m and m.get("swatch"):
        sw = data_uri(os.path.join(root, m["swatch"]), max_edge=80)
        return f'<span class="mi"><i style="background-image:url({sw})"></i>{esc(m.get("name", prettify(val)))}</span>'
    if m:
        return f'<span class="mi"><i class="txt"></i>{esc(m.get("name", prettify(val)))}</span>'
    return esc(prettify(val))


# ---------- metadata table ----------
def spec_table(root, b, bid, palette):
    rows = []
    fin = b.get("finish")
    if not fin and isinstance(b.get("materials"), dict):
        fin = next(iter(b["materials"].values()), None)
    if fin:
        rows.append(("Finish", mat_inline(root, fin, palette)))
    else:
        for tok in re.split(r"[-_ ]+", bid):
            m = match_material(tok, palette)
            if m and m.get("kind") in ("veneer", "laminate"):
                rows.append(("Finish", mat_inline(root, m["key"], palette)))
                break
    if b.get("crockery"):
        rows.append(("Crockery", f'{esc(prettify(b["crockery"]))} (raised 3D reeding)'
                     if str(b["crockery"]).lower() == "fluted" else esc(prettify(b["crockery"]))))
    door = b.get("doors") or b.get("door") or next((v for k, v in DOOR_HINTS.items() if k in bid), None)
    if door and not b.get("crockery"):   # crockery units: room doors live in the Doors section
        rows.append(("Doors", f'{esc(prettify(door))} (incised)' if str(door).lower() == "grooved"
                     else esc(prettify(door))))
    if b.get("edge_banding"):
        rows.append(("Edge banding", esc(prettify(b["edge_banding"]))))
    hnd = b.get("handles")
    if hnd and str(hnd).lower() != "unspecified":
        rows.append(("Handles", mat_inline(root, hnd, palette)))
    else:
        rows.append(("Handles", '<span class="unspec">unspecified</span>'))
    for k in ("inner_fabric", "layout"):
        if b.get(k):
            rows.append((FIELD_LABELS[k], esc(prettify(b[k]))))
    for k, v in b.items():
        if k not in RESERVED:   # custom field → readable key, but keep the value's text as-is
            rows.append((prettify(k), esc(v)))
    trs = "".join(f"<tr><th>{esc(l)}</th><td>{v}</td></tr>" for l, v in rows)
    return f'<table class="spec">{trs}</table>'


def build_visual(udir, bid, max_edge):
    img = os.path.join(udir, "versions", bid + ".png")
    uri = data_uri(img, max_edge=max_edge) if os.path.exists(img) else None
    return (f'<img src="{uri}" alt="{esc(bid)}">' if uri
            else '<div class="missing">image not yet rendered</div>')


def resolve_img(root, udir, img):
    """Resolve an image path from a plan/section: absolute as-is, else relative to the
    unit dir, else relative to the working root (so root-level annotation/ paths work)."""
    if not img:
        return None
    cands = [img] if os.path.isabs(img) else [os.path.join(udir, img), os.path.join(root, img)]
    return next((c for c in cands if os.path.exists(c)), None)


def notes_html(notes, placeholder="Notes / corrections — to be added"):
    if notes:
        return '<ul class="spec-notes">' + "".join(f"<li>{esc(n)}</li>" for n in notes) + "</ul>"
    return f'<div class="notes-ph">✎ {esc(placeholder)}</div>'


def schematics_block(root, udir, plan):
    """Inside-partitions hand-drawn schematic, full-width. plan `schematics: {partitions: <img>}`
    fills it; missing → placeholder. `schematics: false` suppresses the block entirely."""
    sc = plan.get("schematics", {})
    if sc is False:
        return ""
    sc = sc if isinstance(sc, dict) else {}
    p = resolve_img(root, udir, sc.get("partitions"))
    uri = data_uri(p, max_edge=1600) if p else None
    body = (f'<img src="{uri}" alt="Inside partitions">' if uri
            else '<div class="sch-ph">✎ Inside partitions<span>hand-drawn schematic (iPad) — to be added</span></div>')
    return ('<div class="schematics"><div class="sec-label">Inside partitions — hand-drawn</div>'
            f'<figure class="sch-card sch-full">{body}</figure></div>')


def spec_pages_block(root, udir, plan):
    """Per-unit `spec_pages: [{title, image, notes: [..]}]` — each renders as a large
    annotated spec image + bullet notes (placeholder if empty), on its own print page."""
    pages = plan.get("spec_pages") or []
    out = []
    for p in pages:
        title = p.get("title", "Spec / corrections")
        img = resolve_img(root, udir, p.get("image"))
        uri = data_uri(img, max_edge=1600) if img else None
        img_html = (f'<img src="{uri}" alt="{esc(title)}">' if uri
                    else '<div class="sch-ph">✎ spec image — to be added</div>')
        out.append(f'<div class="spec-page"><div class="sec-hd">{esc(title)}</div>'
                   f'<figure class="spec-fig">{img_html}</figure>'
                   f'{notes_html(p.get("notes"))}</div>')
    return "".join(out)


def render_extra_section(root, sec):
    """A standalone top-level section (e.g. pelmets) with note, representative image(s),
    and bullet notes. Reuses the flat/room shell for page-breaks + styling."""
    sid = slug(sec.get("id") or sec.get("title", "section"))
    title = sec.get("title", "Section")
    h = [f'<section class="flat" id="{sid}">'
         f'<div class="flat-banner"><div class="flat-eyebrow">Section</div><h2>{esc(title)}</h2></div></section>'
         f'<div class="room extra-detail" id="{sid}-detail"><div class="room-hd"><div class="eyebrow">Section</div>'
         f'<h3>{esc(title)}</h3></div>']
    if sec.get("note"):
        h.append(f'<p class="idea">{esc(sec["note"])}</p>')
    for im in (sec.get("images") or []):
        p = resolve_img(root, root, im.get("src"))
        uri = data_uri(p, max_edge=1600) if p else None
        cap = f'<figcaption>{esc(im.get("caption",""))}</figcaption>' if im.get("caption") else ""
        h.append(f'<figure class="spec-fig">{f"<img src=\"{uri}\">" if uri else "<div class=\"sch-ph\">✎ image — to be added</div>"}{cap}</figure>')
    h.append(notes_html(sec.get("bullets"), "Notes / bullets — to be added"))
    h.append('</div>')
    return "".join(h)


def render_unit(root, flat, room, unit, pngs, palette):
    udir = os.path.join(root, flat, room, unit)
    plan = load_yaml(os.path.join(udir, "plan.yaml"))
    sel = plan.get("selected")
    sel = set(sel) if isinstance(sel, list) else ({sel} if sel else set())

    declared = plan.get("builds") or plan.get("versions") or []
    builds = {}
    for b in declared:
        if isinstance(b, dict) and (b.get("id") or b.get("v")):
            builds[b.get("id") or b.get("v")] = dict(b)
    for png in pngs:
        name = os.path.splitext(os.path.basename(png))[0]
        builds.setdefault(name, {"id": name})

    selected, considered = [], []
    for bid, b in builds.items():
        status = b.get("status") or ("selected" if bid in sel else "considered")
        if status not in VISIBLE:
            continue
        (selected if (status in LEADING or bid in sel) else considered).append((bid, b))
    if SELECTED_ONLY:
        considered = []

    if not selected and not considered:
        return ""
    h = [f'<div class="unit"><h4>{esc(prettify(unit))}</h4>']
    if plan.get("notes"):
        h.append(f'<p class="unit-notes">{esc(plan["notes"])}</p>')
    if plan.get("todo"):
        h.append(f'<div class="todo-note">☐ TODO — {esc(plan["todo"])}</div>')
    if plan.get("requirements"):
        reqs = "".join(f"<li>{esc(r)}</li>" for r in plan["requirements"])
        h.append(f'<div class="reqs"><div class="sec-label">Requirements</div>'
                 f'<ul class="spec-notes">{reqs}</ul></div>')
    light = f'<div class="ss-light">💡 {esc(plan["lighting"])}</div>' if plan.get("lighting") else ""

    sc = plan.get("schematics")
    sch_img = resolve_img(root, udir, sc.get("partitions")) if isinstance(sc, dict) else None
    combined = bool(selected) and bool(sch_img)   # pair the partition schematic with the selected render

    if selected:
        if not SELECTED_ONLY:
            h.append('<div class="sec-hd sel-hd">✓ Selected</div>')
        for i, (bid, b) in enumerate(selected):
            meta = (f'<div class="ss-meta"><div class="blabel">{esc(b.get("label") or prettify(bid))}</div>'
                    f'{spec_table(root, b, bid, palette)}{light if i == 0 else ""}</div>')
            if combined and i == 0:
                schuri = data_uri(sch_img, max_edge=1800)
                h.append('<div class="spec-sheet withsch">'
                         f'<div class="ss-top">{build_visual(udir, bid, 1200)}{meta}</div>'
                         f'<figure class="sch-in"><img src="{schuri}" alt="Inside partitions">'
                         '<figcaption>Inside partitions — hand-drawn</figcaption></figure></div>')
            else:
                h.append(f'<div class="spec-sheet">{build_visual(udir, bid, 920)}{meta}</div>')
    if light and not selected:
        h.append(light)

    if considered:
        h.append('<div class="sec-hd">Considered <span>— alternatives for your input</span></div>'
                 '<div class="build-grid">')
        for bid, b in considered:
            h.append(f'<figure class="build">{build_visual(udir, bid, 560)}'
                     f'<figcaption><div class="blabel">{esc(b.get("label") or prettify(bid))}</div>'
                     f'{spec_table(root, b, bid, palette)}</figcaption></figure>')
        h.append('</div>')

    if room != "doors" and not combined:   # combined already placed the schematic beside the render
        h.append(schematics_block(root, udir, plan))
    h.append(spec_pages_block(root, udir, plan))

    interior = plan.get("interior", {}) or {}
    if interior.get("spec") or interior.get("image"):
        h.append('<div class="interior"><div class="sec-label">Interior / compartments</div>')
        if interior.get("spec"):
            h.append(f'<p>{esc(interior["spec"])}</p>')
        if interior.get("image"):
            uri = data_uri(os.path.join(udir, interior["image"]), max_edge=900)
            if uri:
                h.append(f'<img class="isketch" src="{uri}" alt="interior">')
        h.append('</div>')

    prog = plan.get("progress") or {}
    if prog:
        pills = []
        for k, v in prog.items():
            cls, txt = ("done", "✓ done") if v is True else \
                       ("pend", "○ pending") if v in (False, None) else ("info", esc(v))
            pills.append(f'<span class="pg pg-{cls}"><b>{esc(prettify(k))}</b> {txt}</span>')
        h.append('<div class="progress"><div class="sec-label">Status</div>'
                 f'<div class="pills">{"".join(pills)}</div></div>')
    h.append('</div>')
    return "".join(h)


def img_or_missing(uri):
    return f'<img src="{uri}">' if uri else '<div class="missing">image not yet rendered</div>'


def render_merged_room(root, flat, room, units_dict, palette):
    """A room whose units are walls of one thing (e.g. kitchen wall-1/wall-2): state the
    decision + metadata ONCE, show every wall image together."""
    walls = sorted(units_dict)
    plan = load_yaml(os.path.join(root, flat, room, walls[0], "plan.yaml"))  # walls share the spec
    sel = plan.get("selected")
    sel = set(sel) if isinstance(sel, list) else ({sel} if sel else set())
    builds = {(b.get("id") or b.get("v")): b for b in (plan.get("builds") or []) if isinstance(b, dict)}
    for wall in walls:
        for png in units_dict[wall]:
            builds.setdefault(os.path.splitext(os.path.basename(png))[0], {"id": None})

    def wall_figs(bid, edge):
        figs = []
        for wall in walls:
            p = os.path.join(root, flat, room, wall, "versions", bid + ".png")
            uri = data_uri(p, edge) if os.path.exists(p) else None
            figs.append(f'<figure class="wallfig">{img_or_missing(uri)}'
                        f'<figcaption>{esc(prettify(wall))}</figcaption></figure>')
        return "".join(figs)

    selected, considered = [], []
    for bid, b in builds.items():
        status = b.get("status") or ("selected" if bid in sel else "considered")
        if status not in VISIBLE:
            continue
        (selected if (status in LEADING or bid in sel) else considered).append((bid, b))
    if SELECTED_ONLY:
        considered = []
    if not selected and not considered:
        return ""

    h = [f'<div class="unit"><h4>{esc(prettify(room))}</h4>'
         f'<p class="unit-notes">One kitchen, {len(walls)} walls — shown together below.</p>']
    if plan.get("notes"):
        h.append(f'<p class="unit-notes">{esc(plan["notes"])}</p>')
    if plan.get("todo"):
        h.append(f'<div class="todo-note">☐ TODO — {esc(plan["todo"])}</div>')
    if plan.get("requirements"):
        reqs = "".join(f"<li>{esc(r)}</li>" for r in plan["requirements"])
        h.append(f'<div class="reqs"><div class="sec-label">Requirements</div>'
                 f'<ul class="spec-notes">{reqs}</ul></div>')
    light = f'<div class="ss-light">💡 {esc(plan["lighting"])}</div>' if plan.get("lighting") else ""
    for i, (bid, b) in enumerate(selected):
        if not SELECTED_ONLY:
            h.append('<div class="sec-hd sel-hd">✓ Selected</div>')
        h.append(f'<div class="ktchn"><div class="wallgrid">{wall_figs(bid, 760)}</div>'
                 f'<div class="ss-meta"><div class="blabel">{esc(b.get("label") or prettify(bid))}</div>'
                 f'{spec_table(root, b, bid, palette)}{light if i == 0 else ""}</div></div>')
    if considered:
        h.append('<div class="sec-hd">Considered <span>— alternatives for your input</span></div>')
        for bid, b in considered:
            h.append(f'<div class="ktchn con"><div class="wallgrid">{wall_figs(bid, 520)}</div>'
                     f'<div class="ss-meta"><div class="blabel">{esc(b.get("label") or prettify(bid))}</div>'
                     f'{spec_table(root, b, bid, palette)}</div></div>')
    udir0 = os.path.join(root, flat, room, walls[0])
    # merged rooms (e.g. kitchen) have no single inside-partitions schematic — they use spec_pages.
    # Only show the schematic if a partition image is actually provided (no empty placeholder).
    if isinstance(plan.get("schematics"), dict) and resolve_img(root, udir0, plan["schematics"].get("partitions")):
        h.append(schematics_block(root, udir0, plan))
    h.append(spec_pages_block(root, udir0, plan))
    prog = plan.get("progress") or {}
    if prog:
        pills = []
        for k, v in prog.items():
            cls, txt = ("done", "✓ done") if v is True else \
                       ("pend", "○ pending") if v in (False, None) else ("info", esc(v))
            pills.append(f'<span class="pg pg-{cls}"><b>{esc(prettify(k))}</b> {txt}</span>')
        h.append('<div class="progress"><div class="sec-label">Status</div>'
                 f'<div class="pills">{"".join(pills)}</div></div>')
    h.append('</div>')
    return "".join(h)


def pal_card(root, m):
    sw = m.get("swatch")
    uri = data_uri(os.path.join(root, sw), max_edge=360) if sw else None
    todo = m.get("status") == "todo"
    if uri:
        thumb = f'<div class="sw" style="background-image:url({uri})"></div>'
    elif todo:
        thumb = '<div class="sw todo">to be selected</div>'
    else:
        thumb = '<div class="sw text">text</div>'
    used = ", ".join(m.get("used_in", []) or [])
    # in the selected edition every material shown IS selected, so the ★ badge is redundant
    lead = m.get("status", "") in LEADING and not SELECTED_ONLY
    badge = ('<span class="lead">★ selected</span>' if lead
             else '<span class="todo-b">☐ TODO</span>' if todo else "")
    cls = " is-lead" if lead else (" is-todo" if todo else "")
    return (f'<div class="pal-card{cls}">{thumb}<div class="pal-meta">'
            f'<div class="pal-name">{esc(m.get("name", m.get("key","")))}{badge}</div>'
            f'<div class="pal-kind">{esc(m.get("kind",""))}</div>'
            + (f'<div class="pal-used">{esc(used)}</div>' if used else "") + '</div></div>')


def flat_colours(root, palette, flat):
    # only the chosen scheme (selected/leading) + still-pending tiles; alternatives live in the full palette
    mats = [m for m in palette if used_here(m, flat)
            and (m.get("status") in LEADING or m.get("status") == "todo")]
    if not mats:
        return ""
    groups = []
    for kind in KIND_ORDER + sorted({m.get("kind", "other") for m in mats} - set(KIND_ORDER)):
        g = [m for m in mats if m.get("kind", "other") == kind]
        if not g:
            continue
        chips = []
        for m in g:
            sw = m.get("swatch")
            uri = data_uri(os.path.join(root, sw), max_edge=220) if sw else None
            cls = ("chip" + ("" if uri else " text") + (" lead" if m.get("status", "") in LEADING else "")
                   + (" todo" if m.get("status") == "todo" else ""))
            chips.append(f'<div class="{cls}" style="{f"background-image:url({uri})" if uri else ""}">'
                         f'<span>{esc(m.get("name",""))}</span></div>')
        groups.append(f'<div class="cw-group"><div class="cw-kind">{esc(kind)}</div>'
                      f'<div class="chips">{"".join(chips)}</div></div>')
    return f'<div class="colourway"><div class="sec-label">Colourway</div>{"".join(groups)}</div>'


def sel_descriptor(root, udir, palette):
    plan = load_yaml(os.path.join(udir, "plan.yaml"))
    sel = plan.get("selected")
    if isinstance(sel, list):
        sel = sel[0] if sel else None
    if not sel:
        return None
    builds = {(b.get("id") or b.get("v")): b for b in (plan.get("builds") or []) if isinstance(b, dict)}
    b = builds.get(sel, {"id": sel})
    fin, finname = b.get("finish"), None
    if fin:
        finname = (match_material(str(fin), palette) or {}).get("name", prettify(fin))
    else:
        for tok in re.split(r"[-_ ]+", sel):
            m = match_material(tok, palette)
            if m and m.get("kind") in ("veneer", "laminate"):
                finname = m["name"]
                break
    parts = [finname or prettify(sel)]
    if b.get("crockery"):
        parts.append(f"{prettify(b['crockery'])} crockery")
    door = b.get("doors") or b.get("door") or next((v for k, v in DOOR_HINTS.items() if k in sel), None)
    if door and door != "plain" and not b.get("crockery"):
        parts.append(f"{prettify(door)} doors")
    if b.get("edge_banding"):
        parts.append(prettify(b["edge_banding"]).split(" (")[0])
    return " · ".join(parts)


def selections_summary(root, tree, palette, area_order):
    flats = sorted(tree)
    merged = set()   # wall-rooms (e.g. kitchen) → one row, not per wall
    for flat in flats:
        for room, units in tree[flat].items():
            if len(units) > 1 and all(u.startswith("wall") for u in units):
                merged.add(room)
    keys = []
    for flat in flats:
        for room in ordered_rooms(flat, tree[flat], area_order):
            if room in merged:
                if (room, None) not in keys:
                    keys.append((room, None))
            else:
                for unit in sorted(tree[flat][room]):
                    if (room, unit) not in keys:
                        keys.append((room, unit))
    room_rank = {}
    for i, aid in enumerate(area_order):
        p = aid.split("/", 1)
        if len(p) == 2 and p[1] not in room_rank:
            room_rank[p[1]] = i
    keys.sort(key=lambda rk: (room_rank.get(rk[0], 10000), room_key(rk[0]), rk[1] or ""))

    def cell_desc(flat, room, unit):
        rooms = tree.get(flat, {})
        if room not in rooms:
            return None, '<span class="na">—</span>'
        if unit is None:
            walls = sorted(rooms[room])
            udir = os.path.join(root, flat, room, walls[0]) if walls else None
        elif unit in rooms[room]:
            udir = os.path.join(root, flat, room, unit)
        else:
            return None, '<span class="na">—</span>'
        desc = sel_descriptor(root, udir, palette) if udir else None
        return desc, (esc(desc) if desc else '<span class="tbd">in consideration</span>')

    rows, any_sel = [], False
    for room, unit in keys:
        cells = []
        for flat in flats:
            desc, html = cell_desc(flat, room, unit)
            if desc:
                any_sel = True
            cells.append(html)
        label = prettify(room) if unit is None else f"{prettify(room)} / {prettify(unit)}"
        rows.append((label, cells))
    if not any_sel:
        return ""
    head = "".join(f"<th>{esc(prettify(f))}</th>" for f in flats)
    body = "".join(f'<tr><td class="u">{esc(lbl)}</td>' + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
                   for lbl, cells in rows)
    return ('<section class="summary"><h2>Selections at a glance</h2>'
            f'<table class="sumtable"><thead><tr><th>Unit</th>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table>'
            '<div class="sum-note">Current leading choice per unit. '
            + ('Selected specifications below.' if SELECTED_ONLY else 'Full options + metadata below.')
            + '</div></section>')


def main():
    global SELECTED_ONLY
    argv = sys.argv[1:]
    SELECTED_ONLY = "--selected-only" in argv
    pos = [a for a in argv if not a.startswith("--")]
    if not pos:
        sys.exit(__doc__)
    root = os.path.abspath(pos[0])
    default_name = "design-book-selected.html" if SELECTED_ONLY else "design-book.html"
    out = pos[1] if len(pos) > 1 else os.path.join(root, default_name)

    design = load_yaml(os.path.join(root, "design.yaml"))
    project = design.get("project") or os.path.basename(root)
    brief = design.get("brief", "")
    palette = design.get("palette", []) or []
    areas = {a["id"]: a for a in (design.get("areas") or []) if "id" in a}
    area_order = list(areas)

    tree = {}
    for png in glob.glob(os.path.join(root, "*", "*", "*", "versions", "*.png")):
        rel = os.path.relpath(png, root).split(os.sep)
        if len(rel) == 5:
            tree.setdefault(rel[0], {}).setdefault(rel[1], {}).setdefault(rel[2], []).append(png)
    for pp in glob.glob(os.path.join(root, "*", "*", "*", "plan.yaml")):
        rel = os.path.relpath(pp, root).split(os.sep)
        if len(rel) == 4:
            tree.setdefault(rel[0], {}).setdefault(rel[1], {}).setdefault(rel[2],
                tree.get(rel[0], {}).get(rel[1], {}).get(rel[2], []))

    for h in (design.get("hide") or []):   # skip duplicate/omitted rooms or units
        parts = h.split("/")
        if len(parts) == 2 and parts[0] in tree:
            tree[parts[0]].pop(parts[1], None)
        elif len(parts) == 3 and parts[1] in tree.get(parts[0], {}):
            tree[parts[0]][parts[1]].pop(parts[2], None)
    for flat in list(tree):
        for room in list(tree[flat]):
            if not tree[flat][room]:
                del tree[flat][room]
        if not tree[flat]:
            del tree[flat]

    P = [HEAD.replace("{{PROJECT}}", esc(project))]
    cover_sub = ('Interior design book · Selected edition · ' if SELECTED_ONLY
                 else 'Interior design book · ') + esc(", ".join(sorted(tree)))
    disclaimer = ('<div class="disclaimer"><b>⚠ Renders are approximate &amp; representative only.</b> '
                  'They do not reproduce exact material colours, and they do not maintain exact layout, '
                  'proportions, or dimensions. Do <b>not</b> use them as a reference for execution — refer to '
                  'the written specifications, physical material samples, and on-site measurements.</div>')
    P.append(f'<section class="cover"><h1>{esc(project)}</h1>'
             f'<div class="sub">{cover_sub}</div>'
             + (render_brief(brief) if brief else "")
             + disclaimer + '</section>')

    P.append(selections_summary(root, tree, palette, area_order))
    # (Contents/TOC removed — the "Selections at a glance" summary serves as the overview.)

    if palette:
        # selected edition: show only chosen (leading/selected) + still-pending (todo) materials
        pal = ([m for m in palette if m.get("status") in LEADING or m.get("status") == "todo"]
               if SELECTED_ONLY else palette)
        P.append('<section class="palette" id="palette"><h2>Material palette</h2>')
        for kind in KIND_ORDER + sorted({m.get("kind", "other") for m in pal} - set(KIND_ORDER)):
            group = [m for m in pal if m.get("kind", "other") == kind]
            if group:
                P.append(f'<div class="pal-kind-h">{esc(kind)}</div><div class="pal-grid">')
                P += [pal_card(root, m) for m in group]
                P.append('</div>')
        P.append('</section>')

    flat_palettes = design.get("flat_palettes") or {}
    for flat in sorted(tree):
        fl = esc(prettify(flat))
        cw = flat_colours(root, palette, flat)
        pimg = resolve_img(root, root, flat_palettes.get(flat))
        if pimg:
            puri = data_uri(pimg, max_edge=1600)
            body = (f'<div class="cw-layout">{cw or "<div></div>"}'
                    f'<figure class="cw-palette"><img src="{puri}" alt="Full palette — {fl}">'
                    '<figcaption>Full palette — physical samples</figcaption></figure></div>')
        else:
            body = cw
        P.append(f'<section class="flat" id="{slug(flat)}">'
                 f'<div class="flat-banner"><div class="flat-eyebrow">Flat</div><h2>{fl}</h2></div>'
                 + body + '</section>')
        for room in ordered_rooms(flat, tree[flat], area_order):
            units = tree[flat][room]
            if len(units) > 1 and all(u.startswith("wall") for u in units):
                body = render_merged_room(root, flat, room, units, palette)
            else:
                body = "".join(render_unit(root, flat, room, unit, units[unit], palette)
                               for unit in sorted(units))
            empty = not body.strip()   # nothing to show yet (TBD) — condense, don't take a whole page
            idea = areas.get(f"{flat}/{room}", {}).get("idea")
            P.append(f'<div class="room{" room-empty" if empty else ""}" id="{slug(flat, room)}">'
                     f'<div class="room-hd"><div class="eyebrow">{fl}</div><h3>{esc(prettify(room))}</h3></div>'
                     + (f'<p class="idea">{esc(idea)}</p>' if idea else "")
                     + (body or '<div class="tbd-tag">◇ To be designed — details &amp; drawings pending.</div>')
                     + '</div>')

    for sec in (design.get("sections") or []):
        P.append(render_extra_section(root, sec))

    P.append(FOOT)
    with open(out, "w") as f:
        f.write("".join(P))
    print(f"wrote {out}  ({sum(len(r) for r in tree.values())} rooms, {len(tree)} flats)")


HEAD = """<!doctype html><html><head><meta charset="utf-8">
<title>{{PROJECT}} — Design Book</title>
<style>
:root{ --ink:#23201c; --mut:#8a8178; --line:#e7e1d8; --bg:#fbf9f6; --accent:#7a5a3a; --ok:#2f6b32; }
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:13.5px/1.48 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
  -webkit-print-color-adjust:exact;print-color-adjust:exact}
h1,h2,h3,h4{margin:0 0 .3em;font-weight:600;letter-spacing:-.01em}
a{color:var(--accent);text-decoration:none} a:hover{text-decoration:underline}
img{max-width:100%;display:block;border-radius:8px}
section,.room{max-width:1000px;margin:0 auto;padding:24px}
.cover{min-height:56vh;display:flex;flex-direction:column;justify-content:center;border-bottom:1px solid var(--line)}
.cover h1{font-size:40px} .cover .sub{color:var(--mut);font-size:18px;margin-top:4px}
.cover .brief{margin-top:18px;font-size:17px;max-width:none} .cover .note{margin-top:24px;color:var(--mut);font-size:13px}
.cover .disclaimer{margin-top:14px;border:1px solid #d9a441;background:#fdf6e6;color:#7a5a1a;border-radius:7px;padding:7px 12px;font-size:11px;line-height:1.4}
.cover .disclaimer b{color:#8a5410}
.toc-wrap{border-bottom:1px solid var(--line)}
.toc .toc-h{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin-bottom:8px}
.toc ul{list-style:none;margin:0;padding:0;columns:2;gap:40px} .toc ul ul{columns:1;margin:2px 0 8px 14px}
.toc li{margin:2px 0;break-inside:avoid}
.palette h2,.flat-h,.summary h2{border-bottom:2px solid var(--accent);padding-bottom:6px;display:inline-block}
.sumtable{border-collapse:collapse;width:100%;margin-top:14px;font-size:13.5px}
.sumtable th,.sumtable td{border:1px solid var(--line);padding:8px 12px;text-align:left;vertical-align:top}
.sumtable thead th{background:#f4efe8;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}
.sumtable td.u{font-weight:600;white-space:nowrap}
.sumtable .tbd{color:var(--mut);font-style:italic} .sumtable .na{color:#cfc7bb}
.sum-note{color:var(--mut);font-size:12.5px;margin-top:8px}
.pal-note{color:var(--mut);font-size:13px;margin:8px 0 2px;font-style:italic}
.pal-kind-h{font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--accent);margin:20px 0 8px;font-weight:600}
.pal-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px}
.pal-card{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fff}
.pal-card.is-lead{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.sw{height:96px;background-size:cover;background-position:center}
.sw.text,.chip.text i,.mi i.txt{background:repeating-linear-gradient(45deg,#f2ede6,#f2ede6 6px,#ece5db 6px,#ece5db 12px)}
.sw.text{display:flex;align-items:center;justify-content:center;color:var(--mut)}
.sw.todo{display:flex;align-items:center;justify-content:center;color:var(--mut);font-size:11px;text-align:center;padding:4px;
  background:repeating-linear-gradient(45deg,#faf7f2,#faf7f2 6px,#f1eadf 6px,#f1eadf 12px)}
.pal-card.is-todo{border-style:dashed;border-color:#c9bda9}
.todo-b{color:#a6772e;font-size:10px;font-weight:600;margin-left:6px}
.chip.todo{border-style:dashed;border-color:#c9bda9}
.pal-meta{padding:8px 10px} .pal-name{font-weight:600;font-size:13.5px}
.pal-kind{color:var(--mut);font-size:12px} .pal-used{color:var(--accent);font-size:11.5px;margin-top:3px}
.lead{color:var(--accent);font-size:11px;font-weight:600;margin-left:6px}
.cw-layout{display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:start}
.cw-palette{margin:46px 0 0} .cw-palette img{width:100%;border-radius:10px;border:1px solid var(--line)}
.cw-palette figcaption{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--accent);font-weight:600;margin-top:6px}
.colourway{margin-top:14px} .chips{display:flex;flex-wrap:wrap;gap:10px}
.cw-group{margin-bottom:10px}
.cw-kind{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--accent);margin:8px 0 5px;font-weight:600}
.chip{width:84px;height:84px;border-radius:10px;background-size:cover;background-position:center;border:1px solid var(--line);display:flex;align-items:flex-end}
.chip.lead{box-shadow:0 0 0 2px var(--accent)}
.chip span{font-size:8.5px;background:rgba(255,255,255,.82);width:100%;padding:2px 4px;line-height:1.15}
.flat{padding-top:30px}
.flat-banner{background:var(--accent);color:#fff;border-radius:12px;padding:16px 22px}
.flat-banner h2{color:#fff;border:0;font-size:28px;margin:0;padding:0}
.flat-eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;opacity:.85}
.room{background:#f6f1e9;border:1px solid #e6ddcc;border-radius:14px;padding:16px 20px 20px;margin:26px auto}
.room-empty{padding:12px 20px;margin:10px auto} .room-empty .room-hd{margin-bottom:6px;padding-bottom:7px}
.tbd-tag{color:var(--mut);font-size:12px;font-style:italic;margin-top:2px}
.room-hd{margin-bottom:14px;padding-bottom:11px;border-bottom:2px solid var(--accent)}
.room-hd .eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:var(--accent);font-weight:600}
.room-hd h3{margin:2px 0 0;font-size:18px;color:var(--ink)}
.idea{color:var(--mut);margin:-2px 0 4px}
.unit{border:1px solid var(--line);border-radius:14px;background:#fff;padding:15px;margin:14px 0}
.unit h4{font-size:16px} .unit-notes{color:var(--mut);margin:.2em 0 .7em;font-size:12.5px}
.sec-label{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:18px 0 8px}
.sec-hd{font-size:14px;font-weight:600;margin:20px 0 10px;padding-bottom:5px;border-bottom:1px solid var(--line)}
.sec-hd span{color:var(--mut);font-weight:400;font-size:12.5px}
.sel-hd{color:var(--ok);border-bottom:2px solid var(--ok)}
.spec-sheet{display:grid;grid-template-columns:1.25fr 1fr;gap:18px;align-items:start;
  border:2px solid var(--ok);border-radius:12px;padding:14px;background:#fbfdfb;margin-bottom:8px}
.spec-sheet>img,.spec-sheet .missing{border-radius:8px}
.spec-sheet.withsch{display:block}
.ss-top{display:grid;grid-template-columns:2.4fr 1fr;gap:16px;align-items:start;margin-bottom:12px}
.ss-top>img,.ss-top .missing{width:100%;border-radius:8px;display:block}
.spec-sheet.withsch .ss-meta{margin:0}
.sch-in{margin:0} .sch-in img{width:100%;border:1px solid var(--line);border-radius:8px;display:block}
.sch-in figcaption{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--accent);font-weight:600;margin-top:5px}
.ss-light{font-size:11.5px;color:#6b5a2a;margin-top:8px;padding-top:7px;border-top:1px dashed #e7dcc0}
.ss-meta .blabel{font-weight:600;font-size:14px;margin-bottom:6px}
.build-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px}
.build{margin:0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff}
.build img,.build .missing{border-radius:0}
.build figcaption{padding:10px 12px}
.blabel{font-weight:600;font-size:14px;margin-bottom:6px}
.spec{border-collapse:collapse;width:100%;font-size:12px}
.spec th{text-align:left;font-weight:500;color:var(--mut);padding:4px 12px 4px 0;vertical-align:top;white-space:nowrap;width:1%}
.spec td{padding:4px 0;border-bottom:1px solid var(--line)}
.spec tr:last-child td,.spec tr:last-child th{border-bottom:0}
.mi{display:inline-flex;align-items:center;gap:6px}
.mi i{width:16px;height:16px;border-radius:50%;background-size:cover;display:inline-block;border:1px solid var(--line)}
.unspec{color:var(--mut);font-style:italic}
.missing{aspect-ratio:4/3;display:flex;align-items:center;justify-content:center;color:var(--mut);font-size:13px;
  background:repeating-linear-gradient(45deg,#f6f2ec,#f6f2ec 12px,#efe9df 12px,#efe9df 24px)}
.interior p{margin:.2em 0} .isketch{margin-top:8px;max-width:520px}
.schematics{margin-top:16px}
.sch-card{margin:0} .sch-full{width:100%}
.sch-card img{border-radius:10px;border:1px solid var(--line);width:100%}
.sch-ph{border:2px dashed #c9bda9;border-radius:10px;color:#8a7a52;min-height:200px;padding:16px;
  display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;font-size:14px;font-weight:600;gap:5px;
  background:repeating-linear-gradient(45deg,#faf7f2,#faf7f2 10px,#f1eadf 10px,#f1eadf 20px)}
.sch-ph span{font-size:12px;font-weight:400;color:var(--mut)}
.spec-page{margin-top:18px;border-top:1px solid var(--line);padding-top:14px}
.spec-fig{margin:0 0 10px} .spec-fig img{border-radius:10px;border:1px solid var(--line);width:100%}
.spec-fig figcaption{font-size:12px;color:var(--mut);margin-top:5px}
.spec-notes{margin:8px 0 0;padding-left:20px} .spec-notes li{margin:4px 0}
.notes-ph{border:2px dashed #c9bda9;border-radius:10px;color:#8a7a52;padding:14px 16px;font-size:13px;font-weight:600;
  background:repeating-linear-gradient(45deg,#faf7f2,#faf7f2 10px,#f1eadf 10px,#f1eadf 20px);margin-top:8px}
.pills{display:flex;flex-wrap:wrap;gap:8px}
.pg{font-size:12px;border:1px solid var(--line);border-radius:20px;padding:3px 11px;background:#faf7f2}
.pg-done{background:#eaf3ea;border-color:#bcd9bc;color:var(--ok)} .pg-pend{color:var(--mut)} .pg-info{background:#f2ede6}
.cover .brief{display:block} .cover .brief .fintro{font-size:16px} .cover .brief .fline{margin-top:5px;font-size:16px}
.ktchn{border:2px solid var(--ok);border-radius:12px;padding:14px;background:#fbfdfb;margin-bottom:10px}
.ktchn.con{border:1px solid var(--line);background:#fff}
.wallgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.wallfig{margin:0} .wallfig img,.wallfig .missing{border-radius:8px} .wallfig figcaption{font-size:12px;color:var(--mut);margin-top:4px}
.ktchn .blabel{font-size:16px;font-weight:600;margin-bottom:6px}
.todo-note{border:1px dashed #c9a24a;background:#fdf7e8;color:#7a5a1a;border-radius:8px;padding:10px 12px;font-size:13px;margin:10px 0;font-weight:500}
.light-note{border:1px solid #e7dcc0;background:#fdfbf3;color:#6b5a2a;border-radius:8px;padding:9px 12px;font-size:13px;margin:10px 0}
@page{size:A4;margin:9mm}
@media print{
  .toc-wrap{page-break-after:always}
  .flat{page-break-before:always} .room{page-break-before:always}
  .room.extra-detail{page-break-before:avoid}
  .room.room-empty{page-break-before:auto}
  .spec-page{page-break-before:always}
  .room-hd{break-after:avoid} .sec-hd{break-after:avoid}
  .pal-card,.build,.spec-sheet,.wallfig,.sch-card,.spec-fig{break-inside:avoid}
  .spec-sheet img,.build img,.wallfig img{max-height:500px;width:auto}
  .ss-top>img{max-height:400px} .sch-in img{max-height:440px}
  .cover{min-height:auto}
}
@media(max-width:640px){.spec-sheet{grid-template-columns:1fr}}
</style></head><body>"""

FOOT = "</body></html>"

if __name__ == "__main__":
    main()
