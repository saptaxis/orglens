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
.waiting { border:1px solid var(--warn); border-radius:8px; padding:.9rem 1.1rem;
  margin-bottom:1.75rem }
.waiting h2 { font-size:.8rem; text-transform:uppercase; letter-spacing:.06em;
  color:var(--warn); margin:0 0 .5rem }
.waiting li { margin:.3rem 0 }
.waiting .who { font-weight:600 }
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


def render(groups: list[tuple[str, list[tuple[str, str | None, Activity]]]]) -> str:
    """`groups` is [(group label, [(name, prose status, activity), ...]), ...]."""
    waiting = [
        (name, a)
        for _, rows in groups
        for name, _, a in rows
        if a.waiting
    ]
    body = []

    if waiting:
        items = []
        for name, a in waiting:
            if a.blocked:
                items.append(
                    f"<li><span class='who'>{html.escape(name)}</span> — "
                    f"{a.blocked} packet(s) at a gate</li>"
                )
            for q in a.needs:
                first = q.strip().splitlines()[0]
                items.append(
                    f"<li><span class='who'>{html.escape(name)}</span> — "
                    f"{html.escape(first[:160])}</li>"
                )
        body.append(
            "<section class='waiting'><h2>Waiting on you</h2><ul>"
            + "".join(items)
            + "</ul></section>"
        )

    for label, rows in groups:
        if not rows:
            continue
        body.append(f"<h2 class='grp'>{html.escape(label)}</h2>")
        body.extend(_card(n, why, a) for n, why, a in rows)

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
        + f"<footer>rendered {stamp}</footer></main>"
    )


def write(page: str, path: Path) -> Path:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path
