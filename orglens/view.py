"""A page per project, joining the two things that know about it.

`scad view` renders sessions: who ran what, where, for how long. It groups by
project but knows nothing about the work — no plans, no packets, no documents.
orglens knows the artifacts and nothing about the running. Neither is the
question a human actually asks, which is *where does this project stand*.

They join on `project`, which both resolve identically, and the join happens
over scad's sqlite index rather than its Python: a database is a stable
interface between two repos and an import is not.

Nothing here is stored. Every number is recomputed on render, so the page
cannot go stale the way the hand-written status line it replaces did — the
worst it can be is closed.
"""

from __future__ import annotations

import html
import time
from pathlib import Path

from orglens.activity import Activity

CSS = """
:root { color-scheme: light dark;
  --bg:#fff; --fg:#111; --dim:#666; --line:#e3e3e3; --card:#fafafa; --warn:#b45309; }
@media (prefers-color-scheme: dark) { :root {
  --bg:#111; --fg:#eee; --dim:#999; --line:#2a2a2a; --card:#191919; --warn:#fbbf24; } }
* { box-sizing:border-box }
body { margin:0; padding:2rem 1.5rem; background:var(--bg); color:var(--fg);
  font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",sans-serif; }
main { max-width:1000px; margin:0 auto }
h1 { font-size:1.1rem; font-weight:600; margin:0 0 .25rem }
.sub { color:var(--dim); font-size:.82rem; margin-bottom:1.75rem }
.badge { display:inline-block; border:1px solid var(--warn); color:var(--warn);
  border-radius:999px; padding:.15rem .6rem; font-size:.75rem; font-weight:600;
  margin-bottom:1.5rem }
.badge.clear { border-color:var(--line); color:var(--dim); font-weight:400 }
details.card > summary { cursor:pointer; list-style:none; outline:none }
details.card > summary::-webkit-details-marker { display:none }
details.card[open] { background:transparent }
.detail { margin-top:.75rem; padding-top:.7rem; border-top:1px solid var(--line);
  font-size:.83rem }
.detail h4 { font-size:.7rem; text-transform:uppercase; letter-spacing:.06em;
  color:var(--dim); margin:.7rem 0 .25rem; font-weight:600 }
.detail h4:first-child { margin-top:0 }
.detail a { color:inherit; text-decoration:none; border-bottom:1px solid var(--line) }
.detail a:hover { border-bottom-color:var(--fg) }
.ask { color:var(--warn); margin:.2rem 0 }
.pill { display:inline-block; border:1px solid var(--line); border-radius:4px;
  padding:0 .35rem; margin:0 .25rem .25rem 0; font-size:.76rem }
.cp { cursor:pointer; color:var(--dim); margin-left:.3rem; font-size:.8em;
  user-select:none }
.cp:hover { color:var(--fg) }
.cp.done { color:var(--warn) }
h2.grp { font-size:.78rem; text-transform:uppercase; letter-spacing:.07em;
  color:var(--dim); margin:1.75rem 0 .6rem; border-bottom:1px solid var(--line);
  padding-bottom:.3rem }
.card { border:1px solid var(--line); border-radius:8px; background:var(--card);
  padding:.85rem 1.05rem; margin-bottom:.6rem }
.card.idle { opacity:.55 }
.top { display:flex; justify-content:space-between; align-items:baseline; gap:1rem }
.name { font-weight:600 }
.facts { color:var(--dim); font-size:.82rem; font-variant-numeric:tabular-nums }
.why { margin-top:.3rem; font-size:.9rem }
.notes { margin-top:.5rem; font-size:.8rem; color:var(--dim) }
.notes b { color:var(--fg); font-weight:500 }
.gate { color:var(--warn); font-weight:600 }
ul { margin:0; padding-left:1.1rem }
footer { margin-top:2.5rem; color:var(--dim); font-size:.75rem }
"""


def ago(ts: int | None) -> str:
    if not ts:
        return "—"
    hours = (time.time() - ts) / 3600
    if hours < 1:
        return "just now"
    if hours < 24:
        return f"{hours:.0f}h ago"
    if hours < 24 * 60:
        return f"{hours / 24:.0f}d ago"
    return f"{hours / 720:.0f}mo ago"


def _facts(a: Activity) -> str:
    bits = []
    if a.plan:
        bits.append(f"plan {a.plan}")
    if a.packets:
        gate = f" <span class='gate'>{a.blocked} at a gate</span>" if a.blocked else ""
        bits.append(f"{a.packets} packet{'s' * (a.packets != 1)}{gate}")
    if a.sessions:
        who = "/".join(a.agents) if a.agents else "?"
        bits.append(f"{a.sessions} sessions ({who}) · {a.turns:,} turns")
    if a.dirty:
        bits.append(f"{a.dirty} uncommitted")
    bits.append(ago(a.touched))
    return " · ".join(bits)


def doc_url(path: Path, docs_root: Path, base: str) -> str:
    """The served URL for a path in the tree.

    mkdocs with `directory_urls` — the default — publishes `a/b.md` at `/a/b/`
    and `a/index.md` at `/a/`. The `docs/` prefix is the serving root and does
    not appear in the URL.
    """
    try:
        rel = Path(path).resolve().relative_to(Path(docs_root).resolve())
    except ValueError:
        return "file://" + str(path)
    if rel.suffix == ".md":
        rel = rel.with_suffix("")
        if rel.name == "index":
            rel = rel.parent
    tail = "" if str(rel) == "." else f"{rel}/"
    return f"{base}/{tail}"


def _link(path, label: str, ctx: dict) -> str:
    """Click opens the served doc; the copy affordance yields the real path."""
    url = doc_url(path, ctx["docs_root"], ctx["base_url"])
    fs = html.escape(str(path))
    return (
        f"<a href='{html.escape(url)}' title='{fs}'>{html.escape(label)}</a>"
        f"<span class='cp' data-path='{fs}' title='copy path'>&#x2398;</span>"
    )


def _detail(row: dict, ctx: dict) -> str:
    """What the taxonomy knows, once you ask. Links point into the tree."""
    a, out = row["activity"], []

    if a.needs or a.blocked:
        out.append("<h4>Waiting</h4>")
        if a.blocked:
            out.append(f"<div class='ask'>{a.blocked} workflow packet(s) at a gate</div>")
        for q in a.needs:
            out.append(f"<div class='ask'>{html.escape(q.strip()[:400])}</div>")

    for label, items in row["artifacts"]:
        if not items:
            continue
        out.append(f"<h4>{html.escape(label)} ({len(items)})</h4><div>")
        for art in items[-8:]:
            out.append(f"<span class='pill'>{_link(art.path, art.name, ctx)}</span>")
        out.append("</div>")

    if row.get("docs"):
        out.append(f"<h4>Documents ({len(row['docs'])})</h4><div>")
        for d in row["docs"]:
            out.append(f"<span class='pill'>{_link(d, d.name, ctx)}</span>")
        out.append("</div>")

    if row["dirs"]:
        out.append("<h4>Directories</h4><div>")
        for d in row["dirs"]:
            out.append(f"<span class='pill'>{_link(d, d.name + '/', ctx)}</span>")
        out.append("</div>")

    if a.notes:
        out.append("<h4>Notes</h4>")
        for n in a.notes[:8]:
            where = "" if n["written_in"] == row["name"] else f" · written in {n['written_in']}"
            out.append(
                f"<div>{html.escape(str(n['topic']))} — "
                f"{html.escape(str(n['title'] or '')[:96])}"
                f"<span style='color:var(--dim)'>{html.escape(where)}</span></div>"
            )

    out.append(f"<h4>Root</h4><div>{_link(row['path'], str(row['path']), ctx)}</div>")
    return "<div class='detail'>" + "".join(out) + "</div>"


def _card(name: str, why: str | None, a: Activity) -> str:
    idle = "" if (a.dirty or a.waiting or (a.touched and time.time() - a.touched < 86400 * 14)) else " idle"
    out = [f"<div class='card{idle}'><div class='top'><span class='name'>{html.escape(name)}</span>"
           f"<span class='facts'>{_facts(a)}</span></div>"]
    if why:
        out.append(f"<div class='why'>{html.escape(why)}</div>")
    if a.notes:
        recent = ", ".join(
            f"<b>{html.escape(str(n['topic']))}</b>" for n in a.notes[:4]
        )
        more = f" +{len(a.notes) - 4}" if len(a.notes) > 4 else ""
        out.append(f"<div class='notes'>{len(a.notes)} note(s): {recent}{more}</div>")
    elif a.sessions > 50:
        out.append(
            "<div class='notes'>no notes — "
            f"{a.turns:,} turns of work with nothing captured</div>"
        )
    out.append("</div>")
    return "".join(out)


def _recency(row: dict) -> int:
    a = row["activity"]
    return max(a.touched or 0, a.last_session or 0)


def render(groups: list[tuple[str, list[dict]]], ctx: dict) -> str:
    """`groups` is [(label, [row, ...]), ...]; a row is what `cli.view` builds.

    Ordered by use — most recently touched first — because the question is
    almost always about what you were last doing, not what is alphabetically
    first. The badge counts; the detail lives in the card it belongs to.
    """
    open_items = sum(r["activity"].waiting for _, rows in groups for r in rows)
    projects = len([r for _, rows in groups for r in rows if r["activity"].waiting])
    body = []

    if open_items:
        body.append(
            f"<div class='badge'>{open_items} waiting on you"
            f" · {projects} project{'s' * (projects != 1)}</div>"
        )
    else:
        body.append("<div class='badge clear'>nothing waiting</div>")

    for label, rows in groups:
        if not rows:
            continue
        body.append(f"<h2 class='grp'>{html.escape(label)}</h2>")
        for row in sorted(rows, key=_recency, reverse=True):
            card = _card(row["name"], row["why"], row["activity"])
            body.append(
                card.replace("<div class='card", "<details class='card", 1)
                .replace("<div class='top'>", "<summary><div class='top'>", 1)
                .replace("</div></div>", "</div></summary>", 1)
                + _detail(row, ctx)
                + "</details>"
            )

    stamp = time.strftime("%Y-%m-%d %H:%M")
    return (
        "<!doctype html><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>orglens — where things stand</title>"
        f"<style>{CSS}</style><main>"
        "<h1>Where things stand</h1>"
        "<div class='sub'>Derived on render — plans and packets from the tree, "
        "sessions and notes from scad. Nothing here is stored, so nothing here "
        "can be stale.</div>"
        + "".join(body)
        + f"<footer>rendered {stamp} · links open {html.escape(ctx['base_url'])}"
        " · &#x2398; copies the path</footer></main>"
        "<script>document.addEventListener('click',e=>{"
        "const c=e.target.closest('.cp'); if(!c) return; e.preventDefault();"
        "navigator.clipboard.writeText(c.dataset.path).then(()=>{"
        "c.classList.add('done'); setTimeout(()=>c.classList.remove('done'),900);});"
        "});</script>"
    )


def write(page: str, path: Path) -> Path:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path
