"""A page per project, joining the two things that know about it.

`scad view` renders sessions: who ran what, where, for how long. It groups by
project but knows nothing about the work — no plans, no packets, no documents.
orglens knows the artifacts and nothing about the running. Neither is the
question a human actually asks, which is *where does this project stand*.

orglens asks scad for its sessions (`scad session ls --json`) and its notes
(`scad notes ls --about`) and joins them to units itself; it never opens
scad's index file. A command's output is a contract between two repos and a
schema is not.

Nothing here is stored. Every number is recomputed on render, so the page
cannot go stale the way the hand-written status line it replaces did — the
worst it can be is closed.
"""

from __future__ import annotations

import html
import re
import time
from pathlib import Path

from orglens.activity import Activity, recency
from orglens.sessions import listed

CSS = """
:root { color-scheme: light dark;
  --bg:#f8f5ee; --fg:#2a2622; --dim:#7a7168; --line:#e2dccf; --card:#fffdf8;
  --warn:#a05a1c; --ok:#4c7a3f; --claude:#a3562b; --codex:#2f6f5e; --kimi:#6b4f9a;
  --bar:#f2eee4; }
@media (prefers-color-scheme: dark) { :root {
  --bg:#1b1917; --fg:#ece6da; --dim:#9a9184; --line:#33302b; --card:#242220;
  --warn:#e0a35a; --ok:#8fbf7a; --claude:#d78a5e; --codex:#6fb8a2; --kimi:#b394d8;
  --bar:#211f1c; } }
* { box-sizing:border-box }
body { margin:0; padding:0 1.5rem 3rem; background:var(--bg); color:var(--fg);
  font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",sans-serif; }
main { max-width:1000px; margin:0 auto }
h1, h2.grp, .name { font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif }
h1 { font-size:1.35rem; font-weight:600; margin:1.6rem 0 .2rem; letter-spacing:.01em }
.sub { color:var(--dim); font-size:.82rem; margin-bottom:1rem }
.filters { position:sticky; top:0; z-index:20; background:var(--bar);
  border:1px solid var(--line); border-radius:8px; padding:.55rem .8rem;
  margin:0 0 1.4rem; display:flex; flex-wrap:wrap; gap:.5rem 1.2rem; align-items:center }
.facet { display:flex; align-items:center; gap:.4rem; flex-wrap:wrap }
.flabel { font-size:.68rem; text-transform:uppercase; letter-spacing:.07em; color:var(--dim) }
.tab, .achip { font:inherit; font-size:.78rem; border:1px solid var(--line); background:transparent;
  color:var(--fg); border-radius:999px; padding:.1rem .6rem; cursor:pointer }
.tab.on, .achip.on { background:var(--fg); color:var(--bg); border-color:var(--fg) }
.tab .n { color:var(--dim); font-size:.7rem; margin-left:.3rem }
.tab.on .n { color:var(--bg); opacity:.8 }
.tab.hot { border-color:var(--warn) }
.achip.claude { color:var(--claude) } .achip.codex { color:var(--codex) } .achip.kimi { color:var(--kimi) }
.achip.on.claude { background:var(--claude); border-color:var(--claude); color:var(--bg) }
.achip.on.codex { background:var(--codex); border-color:var(--codex); color:var(--bg) }
.achip.on.kimi { background:var(--kimi); border-color:var(--kimi); color:var(--bg) }
#find { font:inherit; font-size:.82rem; border:1px solid var(--line); border-radius:6px;
  background:var(--card); color:var(--fg); padding:.2rem .5rem; min-width:16rem }
.badge { display:inline-block; border:1px solid var(--warn); color:var(--warn);
  border-radius:999px; padding:.15rem .6rem; font-size:.75rem; font-weight:600;
  margin-bottom:1.2rem }
.badge.clear { border-color:var(--line); color:var(--dim); font-weight:400 }
.badge.live-badge { border-color:var(--ok); color:var(--ok); margin-right:.4rem }
section.lead { margin-bottom:1.2rem }
section.lead ol.list { padding-left:1.2rem }
section.lead .unit { font-weight:600; margin-right:.4rem }
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
.ask { color:var(--warn); margin:.3rem 0 }
.when { color:var(--dim); font-weight:400; font-size:.92em }
.said { white-space:pre-wrap; color:var(--dim); border-left:2px solid var(--line);
  padding-left:.6rem; margin:.2rem 0 }
ol.list { margin:.2rem 0; padding-left:1.4rem }
ol.list li { margin:.18rem 0; border-left:2px solid transparent; padding-left:.35rem }
ol.list li[data-agent="claude"] { border-left-color:var(--claude) }
ol.list li[data-agent="codex"] { border-left-color:var(--codex) }
ol.list li[data-agent="kimi"] { border-left-color:var(--kimi) }
ol.list li.open { color:var(--warn) }
ol.list li.live, .live { color:var(--ok); font-weight:600 }
.pin { display:inline-block; border:1px solid var(--warn); color:var(--warn);
  border-radius:3px; padding:0 .3rem; margin-right:.4rem; font-size:.72rem }
.pill { display:inline-block; border:1px solid var(--line); border-radius:4px;
  padding:0 .35rem; margin:0 .25rem .25rem 0; font-size:.76rem }
.cp { cursor:pointer; color:var(--dim); margin-left:.3rem; font-size:.8em;
  user-select:none }
.cp:hover { color:var(--fg) }
.cp.done { color:var(--warn) }
h2.grp { font-size:.92rem; font-weight:600; color:var(--fg); margin:1.6rem 0 .5rem;
  border-bottom:1px solid var(--line); padding-bottom:.25rem }
h2.grp .n { color:var(--dim); font-weight:400; font-size:.78rem; margin-left:.4rem }
.card { border:1px solid var(--line); border-radius:8px; background:var(--card);
  padding:.85rem 1.05rem; margin-bottom:.6rem }
.card.idle { opacity:.55 }
.card[hidden], li[hidden], section[hidden], h2[hidden] { display:none }
.top { display:flex; justify-content:space-between; align-items:baseline; gap:1rem }
.name { font-weight:600; font-size:1.02rem }
.facts { color:var(--dim); font-size:.82rem; font-variant-numeric:tabular-nums }
.why { margin-top:.3rem; font-size:.9rem }
.notes { margin-top:.5rem; font-size:.8rem; color:var(--dim) }
.notes b { color:var(--fg); font-weight:500 }
.gate { color:var(--warn); font-weight:600 }
ol.loose li { margin:.45rem 0 }
.sid { font-family:ui-monospace,Menlo,monospace; font-size:.78rem; color:var(--dim) }
.where { color:var(--dim); font-size:.78rem; font-family:ui-monospace,Menlo,monospace }
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
    if a.live_sessions:
        bits.append(f"<span class='live'>&#x25CF; {a.live_sessions} live</span>")
    if a.open_sessions:
        bits.append(f"{a.open_sessions} resumable")
    if a.dirty:
        bits.append(f"{a.dirty} uncommitted")
    # Three clocks, deliberately not merged: what landed, what was touched,
    # and when an agent last spoke. They diverge when work is in flight.
    bits.append(f"edited {ago(a.modified)}")
    if a.touched and a.modified and abs(a.touched - a.modified) > 3600:
        bits.append(f"committed {ago(a.touched)}")
    spoke = (a.last_turn or {}).get("at") or a.last_session
    if spoke:
        bits.append(f"session {ago(spoke)}")
    return " · ".join(bits)


def doc_url(path: Path, roots: Path | list[Path], base: str) -> str:
    """The served URL for a path in the tree.

    mkdocs with `directory_urls` — the default — publishes `a/b.md` at `/a/b/`
    and `a/index.md` at `/a/`. The `docs/` prefix is the serving root and does
    not appear in the URL.

    A unit can span more than one root, so every root is tried in turn and
    the first that contains the path wins — a document under the second root
    must not silently fall back to a `file://` link just because only the
    first was checked. Both sides are resolved before comparing. A bare
    `Path` is still accepted, for the one-root case.
    """
    candidates = [roots] if isinstance(roots, Path) else list(roots)
    resolved = Path(path).resolve()
    for root in candidates:
        try:
            rel = resolved.relative_to(Path(root).resolve())
        except ValueError:
            continue
        if rel.suffix == ".md":
            rel = rel.with_suffix("")
            if rel.name == "index":
                rel = rel.parent
        tail = "" if str(rel) == "." else f"{rel}/"
        return f"{base}/{tail}"
    return "file://" + str(path)


_DATE = re.compile(r"([A-Z][a-z]{2})(\d{2})(\d{4})")


def _filedate(name: str) -> str:
    """The grammar puts MonDDYYYY in plan and log filenames. Surface it."""
    m = _DATE.search(name)
    return f"{m.group(2)} {m.group(1)} {m.group(3)}" if m else ""


def _link(path, label: str, ctx: dict) -> str:
    """Click opens the served doc; the copy affordance yields the real path."""
    url = doc_url(path, ctx["docs_roots"], ctx["base_url"])
    fs = html.escape(str(path))
    return (
        f"<a href='{html.escape(url)}' title='{fs}'>{html.escape(label)}</a>"
        f"<span class='cp' data-path='{fs}' title='copy path'>&#x2398;</span>"
    )


#: Section order inside a card, most actionable first. Artifact headings are
#: matched case-insensitively against the grammar's own type names, so a
#: grammar that adds a type still renders — just at the end.
ARTIFACT_ORDER = ("spec", "plan", "log")


def _detail(row: dict, ctx: dict) -> str:
    """What the taxonomy knows, once you ask. Links point into the tree."""
    a, out = row["activity"], []

    if a.needs or a.blocked:
        out.append("<h4>Waiting</h4>")
        if a.blocked:
            out.append(f"<div class='ask'>{a.blocked} workflow packet(s) at a gate</div>")
        for ask in a.needs:
            when = f"<span class='when'> · asked {ago(ask['at'])}</span>" if ask["at"] else ""
            out.append(
                f"<div class='ask'>{html.escape(ask['question'].strip()[:400])}{when}</div>"
            )

    if a.live:
        out.append(f"<h4>Running now ({len(a.live)})</h4><ol class='list'>")
        for s in a.live:
            out.append(
                f"<li class='live'>&#x25CF; {html.escape(str(s['name'] or s['session'] or '')[:60])}"
                f"<span class='when'> · {html.escape(str(s['cwd'] or '')[-46:])}</span></li>"
            )
        out.append("</ol>")

    if a.recent:
        label = f"Sessions ({len(a.recent)}"
        label += f", {a.open_sessions} resumable)" if a.open_sessions else ")"
        out.append(f"<h4>{label}</h4><ol class='list'>")
        for s in a.recent:
            mark = " class='open'" if s["open"] else ""
            flag = (
                f"<span class='pin'>{html.escape(str(s['outcome']))}</span>"
                if s["open"] else ""
            )
            # `how` says why this session is on this card. On a card for a
            # unit sharing a home, the same session sits on the other card
            # too, and this is what makes that read as intended.
            how = f" · {html.escape(s['how'])}" if s.get("how") else ""
            agent = html.escape(str(s.get("agent") or ""))
            out.append(
                f"<li{mark} data-agent='{agent}'>{flag}{html.escape(str(s['name'] or 'untitled'))[:70]}"
                f"<span class='when'> · {s['agent']} · {s['turns']:,} turns · "
                f"{ago(s['at'])}{how}</span></li>"
            )
        out.append("</ol>")

    if a.last_turn and a.last_turn.get("text"):
        who = a.last_turn.get("role") or "?"
        out.append(
            f"<h4>Last said <span class='when'>· {who} · {ago(a.last_turn['at'])}"
            "</span></h4>"
            f"<div class='said'>{html.escape(a.last_turn['text'].strip()[:240])}</div>"
        )

    if a.notes:
        out.append(f"<h4>Notes ({len(a.notes)})</h4><ol class='list'>")
        for n in a.notes[:8]:
            where = "" if n["written_in"] == row["name"] else f" · written in {n['written_in']}"
            when = f" · {ago(n['at'])}" if n.get("at") else ""
            out.append(
                f"<li><b>{html.escape(str(n['topic']))}</b> — "
                f"{html.escape(str(n['title'] or '')[:110])}"
                f"<span class='when'>{html.escape(where + when)}</span></li>"
            )
        out.append("</ol>")

    if row["dirs"]:
        out.append("<h4>Directories</h4><div>")
        for d in row["dirs"]:
            out.append(f"<span class='pill'>{_link(d, d.name + '/', ctx)}</span>")
        out.append("</div>")

    if row.get("docs"):
        out.append(f"<h4>Documents ({len(row['docs'])})</h4><div>")
        for d in row["docs"]:
            out.append(f"<span class='pill'>{_link(d, d.name, ctx)}</span>")
        out.append("</div>")

    def rank(pair):
        heading = pair[0].lower()
        for i, kind in enumerate(ARTIFACT_ORDER):
            if heading.startswith(kind):
                return i
        return len(ARTIFACT_ORDER)

    for label, items in sorted(row["artifacts"], key=rank):
        if not items:
            continue
        out.append(f"<h4>{html.escape(label)} ({len(items)})</h4><div>")
        for art in items[-8:]:
            out.append(
                f"<span class='pill'>{_link(art.path, art.name, ctx)}"
                f"<span class='when'> {_filedate(art.name)}</span></span>"
            )
        out.append("</div>")

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


def _unattributed(loose: list) -> str:
    """Sessions belonging to no unit, newest first, each with the command
    that resumes it. The copy affordance takes any text, not only a path."""
    from orglens.sessions import short_ids, where
    short = short_ids([s.id for s in loose])
    out = [f"<h2 class='grp'>Unattributed<span class='n'>{len(loose)}</span></h2>"
           "<ol class='list loose'>"]
    for s in loose:
        mark = " open" if s.open else (" live" if s.live else "")
        cmd = f"scad session resume {s.id} --print"
        when = ago(s.when // 1000) if s.when else "—"
        said = " ".join(((s.last_turn or {}).get("text") or "").split())[:160]
        label = s.label or short[s.id]
        out.append(
            f"<li class='{mark.strip()}' data-agent='{html.escape(s.agent)}'>"
            f"<span class='sid'>{html.escape(short[s.id])}</span> "
            f"{html.escape(str(label))[:70]}"
            f"<span class='when'> · {html.escape(s.agent)} · {s.turns:,} turns · {when}</span>"
            f"<span class='cp' data-path='{html.escape(cmd)}' title='copy resume command'>"
            "&#x2398;</span>"
            f"<div class='where'>{html.escape(where(s.cwd))}</div>"
            + (f"<div class='said'>{html.escape(said)}</div>" if said else "")
            + "</li>"
        )
    out.append("</ol>")
    return "".join(out)


def _searchable(row: dict) -> str:
    """Everything the find box matches on a card, lowercased: the unit's
    name, its status line, session labels, note titles, document names."""
    a = row["activity"]
    parts = [row["name"], row.get("why") or ""]
    parts += [str(s.get("name") or "") for s in a.recent]
    parts += [str(s.get("name") or "") for s in a.live]
    parts += [str(n.get("title") or "") + " " + str(n.get("topic") or "") for n in a.notes]
    parts += [d.name for d in row.get("docs", [])]
    parts += [art.name for _, items in row.get("artifacts", []) for art in items]
    return html.escape(" ".join(p for p in parts if p).lower(), quote=True)


def _tabs(rows: list[dict]) -> str:
    """One tab per top-level unit, most recently active first, carrying
    two counts: how much is here, and how much of it wants you. A unit that
    is part of another is filed under that one's tab, so a programme's tab
    holds its experiments.

    Recency, not the alphabet: the unit you were just in is the one you are
    coming back to, and an alphabetical strip buries it wherever its name
    falls.
    """
    top = {r["name"]: r for r in rows if not r.get("part_of")}
    tabs: dict[str, dict] = {}
    for r in rows:
        key = r["name"] if r["name"] in top else (r.get("part_of") or r["name"])
        tab = tabs.setdefault(key, {"sessions": 0, "waiting": 0, "recency": 0})
        a = r["activity"]
        tab["sessions"] += a.sessions
        tab["waiting"] += a.waiting
        tab["recency"] = max(tab["recency"], recency(a))
    out = ["<button class='tab on' data-tab=''>all</button>"]
    for name, tab in sorted(tabs.items(), key=lambda kv: kv[1]["recency"], reverse=True):
        hot = " hot" if tab["waiting"] else ""
        counts = f"{tab['sessions']}"
        if tab["waiting"]:
            counts += f" · {tab['waiting']} waiting"
        out.append(
            f"<button class='tab{hot}' data-tab='{html.escape(name, quote=True)}'>"
            f"{html.escape(name)}<span class='n'>{counts}</span></button>"
        )
    return "".join(out)


def _lead_sections(rows: list[dict]) -> str:
    """What wants you and what is running, across every unit, before the
    cards. Each row names its unit and carries the same data attributes the
    cards do, so the filters scope them together."""
    out = []
    waiting = []
    for r in rows:
        a = r["activity"]
        unit = html.escape(r["name"])
        attrs = f"data-unit='{html.escape(r['name'], quote=True)}' data-parent='{html.escape(r.get('part_of') or '', quote=True)}'"
        if a.blocked:
            waiting.append(f"<li {attrs}><span class='unit'>{unit}</span>"
                           f"<span class='ask'>{a.blocked} workflow packet(s) at a gate</span></li>")
        for ask in a.needs:
            when = f"<span class='when'> · asked {ago(ask['at'])}</span>" if ask.get("at") else ""
            waiting.append(f"<li {attrs}><span class='unit'>{unit}</span>"
                           f"<span class='ask'>{html.escape(ask['question'].strip()[:200])}</span>{when}</li>")
    if waiting:
        out.append(f"<section class='lead' data-sec='waiting'><h2 class='grp'>Waiting on you"
                   f"<span class='n'>{len(waiting)}</span></h2><ol class='list'>"
                   + "".join(waiting) + "</ol></section>")
    running = []
    for r in rows:
        a = r["activity"]
        unit = html.escape(r["name"])
        attrs = f"data-unit='{html.escape(r['name'], quote=True)}' data-parent='{html.escape(r.get('part_of') or '', quote=True)}'"
        for s in a.live:
            running.append(f"<li class='live' {attrs} data-agent='claude'><span class='unit'>{unit}</span>"
                           f"&#x25CF; {html.escape(str(s['name'] or s['session'] or '')[:60])}"
                           f"<span class='when'> · {html.escape(str(s['cwd'] or '')[-46:])}</span></li>")
    if running:
        out.append(f"<section class='lead' data-sec='running'><h2 class='grp'>Running now"
                   f"<span class='n'>{len(running)}</span></h2><ol class='list'>"
                   + "".join(running) + "</ol></section>")
    return "".join(out)


JS = """
const tabs = document.querySelectorAll('.tab'), chips = document.querySelectorAll('.achip');
const find = document.getElementById('find');
let unit = '', agent = '', q = '';
function apply() {
  document.querySelectorAll('[data-unit]').forEach(el => {
    const mine = !unit || el.dataset.unit === unit || el.dataset.parent === unit;
    const agents = (el.dataset.agents || el.dataset.agent || '').split(' ');
    const byAgent = !agent || agents.includes(agent);
    const text = el.dataset.text || el.textContent.toLowerCase();
    const byText = !q || text.includes(q);
    el.hidden = !(mine && byAgent && byText);
  });
  document.querySelectorAll('.card li[data-agent]').forEach(li => {
    li.hidden = !!agent && li.dataset.agent !== agent;
  });
  document.querySelectorAll('h2.grp[data-group]').forEach(h => {
    const any = [...document.querySelectorAll(`[data-group-of='${h.dataset.group}']`)].some(c => !c.hidden);
    h.hidden = !any;
  });
  document.querySelectorAll('section.lead').forEach(sec => {
    sec.hidden = ![...sec.querySelectorAll('li')].some(li => !li.hidden);
  });
}
tabs.forEach(t => t.addEventListener('click', () => {
  unit = t.dataset.tab; tabs.forEach(x => x.classList.toggle('on', x === t)); apply();
}));
chips.forEach(c => c.addEventListener('click', () => {
  agent = c.dataset.agent; chips.forEach(x => x.classList.toggle('on', x === c)); apply();
}));
find.addEventListener('input', () => { q = find.value.trim().toLowerCase(); apply(); });
document.addEventListener('click', e => {
  const c = e.target.closest('.cp'); if (!c) return; e.preventDefault();
  navigator.clipboard.writeText(c.dataset.path).then(() => {
    c.classList.add('done'); setTimeout(() => c.classList.remove('done'), 900); });
});
"""


def render(
    groups: list[tuple[str, list[dict]]], ctx: dict, unattributed: list | None = None
) -> str:
    """`groups` is [(label, [row, ...]), ...]; a row is what `cli.view` builds.
    `unattributed` is the sessions belonging to no unit, rendered last.

    Ordered by use — most recently touched first — because the question is
    almost always about what you were last doing, not what is alphabetically
    first. The page embeds every row and scopes itself in the browser: the
    tabs, the agent chips and the find box hide what does not match, and
    nothing is filtered before render.
    """
    rows = [r for _, group in groups for r in group]
    open_items = sum(r["activity"].waiting for r in rows)
    projects = len([r for r in rows if r["activity"].waiting])
    body = []

    body.append(
        "<div class='filters'>"
        f"<div class='facet'><span class='flabel'>unit</span>{_tabs(rows)}</div>"
        "<div class='facet'><span class='flabel'>agent</span>"
        "<button class='achip on' data-agent=''>all</button>"
        "<button class='achip claude' data-agent='claude'>claude</button>"
        "<button class='achip codex' data-agent='codex'>codex</button>"
        "<button class='achip kimi' data-agent='kimi'>kimi</button></div>"
        "<div class='facet'><span class='flabel'>find</span>"
        "<input id='find' placeholder='unit, session, document, note…' autocomplete='off'></div>"
        "</div>"
    )

    running = sum(r["activity"].live_sessions for r in rows)
    if running:
        body.append(f"<div class='badge live-badge'>&#x25CF; {running} running now</div> ")

    if open_items:
        oldest = min(
            (ask["at"] for r in rows for ask in r["activity"].needs if ask.get("at")),
            default=None,
        )
        age = f" · oldest {ago(oldest)}" if oldest else ""
        body.append(
            f"<div class='badge'>{open_items} waiting on you"
            f" · {projects} unit{'s' * (projects != 1)}{age}</div>"
        )
    else:
        body.append("<div class='badge clear'>nothing waiting</div>")

    body.append(_lead_sections(rows))

    # Groups led by whichever holds the newest member, the same rule `list`
    # uses: the kind that sorts first alphabetically has no claim to the top.
    def newest(group):
        return max((recency(r["activity"]) for r in group), default=0)

    for label, group in sorted(groups, key=lambda g: newest(g[1]), reverse=True):
        if not group:
            continue
        gid = html.escape(label, quote=True)
        body.append(f"<h2 class='grp' data-group='{gid}'>{html.escape(label)}"
                    f"<span class='n'>{len(group)}</span></h2>")
        for row in sorted(group, key=lambda r: recency(r["activity"]), reverse=True):
            a = row["activity"]
            agents = " ".join(sorted({str(s.get("agent") or "") for s in a.recent} - {""}))
            attrs = (
                f" data-unit='{html.escape(row['name'], quote=True)}'"
                f" data-parent='{html.escape(row.get('part_of') or '', quote=True)}'"
                f" data-agents='{agents}' data-group-of='{gid}'"
                f" data-text='{_searchable(row)}'"
            )
            card = _card(row["name"], row["why"], a)
            body.append(
                card.replace("<div class='card", "<details" + attrs + " class='card", 1)
                .replace("<div class='top'>", "<summary><div class='top'>", 1)
                .replace("</div></div>", "</div></summary>", 1)
                + _detail(row, ctx)
                + "</details>"
            )

    loose = listed(unattributed or [])
    if loose:
        body.append(_unattributed(loose))

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
        f"<script>{JS}</script>"
    )


def write(page: str, path: Path) -> Path:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path
