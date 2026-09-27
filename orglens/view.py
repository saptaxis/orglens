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

from orglens import formats
from orglens.activity import MENTIONS, Activity, recency
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
  margin:0 0 1.2rem; display:flex; flex-wrap:wrap; gap:.5rem 1.2rem; align-items:center }
.facet { display:flex; align-items:center; gap:.4rem; flex-wrap:wrap }
.flabel { font-size:.68rem; text-transform:uppercase; letter-spacing:.07em; color:var(--dim) }
.chip { font:inherit; font-size:.78rem; border:1px solid var(--line); background:transparent;
  color:var(--fg); border-radius:999px; padding:.1rem .6rem; cursor:pointer }
.chip.on { background:var(--fg); color:var(--bg); border-color:var(--fg) }
.chip .n { color:var(--dim); font-size:.7rem; margin-left:.3rem }
.chip.on .n { color:var(--bg); opacity:.8 }
.chip.claude { color:var(--claude) } .chip.codex { color:var(--codex) } .chip.kimi { color:var(--kimi) }
.chip.on.claude { background:var(--claude); border-color:var(--claude); color:var(--bg) }
.chip.on.codex { background:var(--codex); border-color:var(--codex); color:var(--bg) }
.chip.on.kimi { background:var(--kimi); border-color:var(--kimi); color:var(--bg) }
#find { font:inherit; font-size:.82rem; border:1px solid var(--line); border-radius:6px;
  background:var(--card); color:var(--fg); padding:.2rem .5rem; min-width:16rem }
.badge { display:inline-block; border:1px solid var(--warn); color:var(--warn);
  border-radius:999px; padding:.15rem .6rem; font-size:.75rem; font-weight:600;
  margin-bottom:1.2rem }
.badge.clear { border-color:var(--line); color:var(--dim); font-weight:400 }
.badge.live-badge { border-color:var(--ok); color:var(--ok); margin-right:.4rem }
details.band > summary { cursor:pointer; list-style:none; outline:none;
  font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  font-size:1rem; font-weight:600; margin:1.4rem 0 .5rem; border-bottom:1px solid var(--line);
  padding-bottom:.25rem; display:flex; align-items:baseline; gap:.5rem }
details.band > summary::-webkit-details-marker { display:none }
details.band > summary::before { content:"▸"; color:var(--dim); font-size:.8rem }
details.band[open] > summary::before { content:"▾" }
details.band > summary .n { color:var(--dim); font-weight:400; font-size:.78rem }
details.band.waiting > summary { color:var(--warn); border-bottom-color:var(--warn) }
.kind { font-size:.68rem; text-transform:uppercase; letter-spacing:.06em; color:var(--dim);
  border:1px solid var(--line); border-radius:4px; padding:0 .35rem; margin-left:.5rem; vertical-align:middle }
.placed { color:var(--fg) }
.why.stale { color:var(--dim) }
.why .age { font-size:.75rem; color:var(--dim); margin-left:.4rem }
.why.stale .age { color:var(--warn) }
.tag { font-size:.72rem; color:var(--warn); border:1px solid var(--warn); border-radius:4px;
  padding:0 .35rem; margin-left:.5rem; vertical-align:middle }
.nested { margin:.6rem 0 0 1rem; border-left:2px solid var(--line); padding-left:.8rem }
.nested .card { margin-bottom:.4rem }
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
.name { font-weight:600; font-size:1.02rem; white-space:nowrap }
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


def ago(ts: int | None, now: float | None = None) -> str:
    if not ts:
        return "—"
    hours = ((time.time() if now is None else now) - ts) / 3600
    if hours < 1:
        return "just now"
    if hours < 24:
        return f"{hours:.0f}h ago"
    if hours < 24 * 60:
        return f"{hours / 24:.0f}d ago"
    return f"{hours / 720:.0f}mo ago"


def doc_url(path: Path, roots: Path | list[Path], base: str) -> str:
    """The served URL for a path in the tree.

    mkdocs with `directory_urls` — the default — publishes `a/b.md` at `/a/b/`
    and `a/index.md` at `/a/`; `a/b.org` is given the same URL. The `docs/` prefix is the serving root and does
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
        if rel.suffix in formats.SUFFIXES:
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
    """Click opens the served doc, or the file itself when `view_link` is
    `file` — the setting for a tree read in an editor rather than served.
    The copy affordance always yields the real path."""
    if ctx.get("link") == "file":
        url = "file://" + str(path)
    else:
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
            # Why this note is here, when it is not simply the unit's own.
            # `written in X` reads as provenance and was the only label;
            # a note that merely names the unit now says so instead of
            # borrowing that sentence.
            how, wrote = n.get("how"), n["written_in"]
            if how == MENTIONS:
                where = f" · mentions this, from {wrote}" if wrote else " · mentions this"
            elif wrote and wrote != row["name"]:
                where = f" · written in {wrote}"
            else:
                where = ""
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


def _unattributed(loose: list) -> str:
    """Sessions belonging to no unit, newest first, each with the commands
    that resume it, claim it, or say it is nobody's.

    Three affordances rather than one, because seeing the pile is not the
    hard part — the hard part was that acting on a row meant retyping a uuid
    into another terminal. `attribute` is offered unfinished, ending in a
    space: **no unit is proposed.** A session here is contained in no home,
    so the cwd suggests nothing by construction, and a unit guessed from a
    title is the containment mistake one layer up. `dismiss --under` carries
    the parent directory, since that is the decision that empties a pile
    where six directories held ~95 of 201 rows.
    """
    from pathlib import Path

    from orglens.sessions import short_ids, where
    short = short_ids([s.id for s in loose])
    out = [f"<h2 class='grp'>Unattributed<span class='n'>{len(loose)}</span></h2>"
           "<ol class='list loose'>"]
    for s in loose:
        mark = " open" if s.open else (" live" if s.live else "")
        cmd = f"scad session resume {s.id} --print"
        claim = f"orglens attribute {s.id} "
        drop = f"orglens dismiss {s.id}"
        parent = str(Path(s.cwd).parent) if s.cwd else None
        sweep = f"orglens dismiss --under {parent}" if parent else None
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
            f"<span class='cp' data-path='{html.escape(claim)}' "
            "title='copy attribute command (add the unit)'>&#x2295;</span>"
            f"<span class='cp' data-path='{html.escape(drop)}' "
            "title='copy dismiss command'>&#x2296;</span>"
            + (f"<span class='cp' data-path='{html.escape(sweep)}' "
               "title='copy dismiss --under for this directory'>&#x229f;</span>"
               if sweep else "")
            + f"<div class='where'>{html.escape(where(s.cwd))}</div>"
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


def write(page: str, path: Path) -> Path:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path


# ── clocks, bands, staleness ─────────────────────────────────────────────
#
# A unit is placed by when it last moved, not by what kind it is. The clocks
# that count, in the order they are trusted: a live session; a session that
# ended; an edit in a home; a commit that touched the unit's own paths. A
# gate — a session that stopped and asked — is not recency at all and puts
# the unit in its own band ahead of every other.

BANDS = ("waiting", "today", "yesterday", "this week", "this month", "earlier")
DAY = 86400


def clocks(a: Activity, now: float | None = None) -> list[tuple[str, int]]:
    """Every clock the unit has, newest first, each named."""
    now = time.time() if now is None else now
    out: list[tuple[str, int]] = []
    if a.needs:
        out.append(("waiting", max((ask.get("at") or 0) for ask in a.needs) or int(now)))
    if a.blocked:
        out.append(("waiting", int(now)))
    # A live process is only "now" while it is talking. An open pane that
    # has not spoken for a day is a pane, not activity; it is placed by
    # when it last spoke and shown as idle.
    for s in a.live:
        spoke = s.get("spoke")
        if spoke is None or now - spoke < DAY:
            out.append(("live", int(now)))
        else:
            out.append(("idle", int(spoke)))
    spoke = (a.last_turn or {}).get("at") or a.last_session
    if spoke:
        out.append(("session", int(spoke)))
    if a.modified:
        out.append(("edited", int(a.modified)))
    if a.touched:
        out.append(("committed", int(a.touched)))
    rank = {"waiting": 0, "live": 1}
    return sorted(out, key=lambda c: (rank.get(c[0], 2), -c[1]))


def band(a: Activity, now: float | None = None) -> str:
    now = time.time() if now is None else now
    cs = clocks(a, now)
    if not cs:
        return "earlier"
    name, at = cs[0]
    if name == "waiting":
        return "waiting"
    age = now - at
    if age < DAY:
        return "today"
    if age < 2 * DAY:
        return "yesterday"
    if age < 7 * DAY:
        return "this week"
    if age < 30 * DAY:
        return "this month"
    return "earlier"


def stale(a: Activity, why_edited: int | None, now: float | None = None) -> bool:
    """The status line is older than the unit's newest movement by more than
    a week: the tree moved and the person's sentence did not."""
    if not why_edited:
        return False
    moved = [at for name, at in clocks(a, now) if name in ("session", "edited", "committed")]
    return bool(moved) and max(moved) - why_edited > 7 * DAY


def _drift_tag(a: Activity, now: float | None = None) -> str:
    """Sessions and edits far apart: talked without landing, or landed
    without a session orglens can see."""
    spoke = (a.last_turn or {}).get("at") or a.last_session
    if not spoke or not a.modified:
        return ""
    if spoke - a.modified > 7 * DAY:
        return "<span class='tag'>talked, nothing landed</span>"
    if a.modified - spoke > 7 * DAY:
        return "<span class='tag'>landed, no session</span>"
    return ""


# ── the page ─────────────────────────────────────────────────────────────


def _placed(a: Activity, now: float) -> str:
    """The one-line reason the unit is where it is: the clock that placed it
    first and in ink, the others after it, then the counts."""
    bits = []
    for i, (name, at) in enumerate(clocks(a, now)):
        if name == "waiting":
            continue
        if name == "live":
            text = "&#x25CF; live"
        elif name == "idle":
            text = f"&#x25CB; open pane, idle {ago(at, now).replace(' ago', '')}"
        else:
            text = f"{name} {ago(at, now)}"
        bits.append(f"<span class='placed'>{text}</span>" if i == 0 else text)
    if a.sessions:
        who = "/".join(a.agents) if a.agents else "?"
        bits.append(f"{a.sessions} sessions ({who})")
    if a.open_sessions:
        bits.append(f"{a.open_sessions} resumable")
    if a.packets:
        gate = f" <span class='gate'>{a.blocked} at a gate</span>" if a.blocked else ""
        bits.append(f"{a.packets} packet{'s' * (a.packets != 1)}{gate}")
    if a.plan:
        bits.append(f"plan {a.plan}")
    if a.dirty:
        bits.append(f"{a.dirty} uncommitted")
    return " · ".join(bits)


def _card(row: dict, ctx: dict, now: float, nested: list[dict] = ()) -> str:
    a = row["activity"]
    name = row["name"]
    agents = " ".join(sorted({str(s.get("agent") or "") for s in a.recent} - {""}))
    why_edited = row.get("why_edited")
    is_stale = stale(a, why_edited, now)
    attrs = (
        f" data-unit='{html.escape(name, quote=True)}'"
        f" data-parent='{html.escape(row.get('part_of') or '', quote=True)}'"
        f" data-kind='{html.escape(row.get('kind') or '', quote=True)}'"
        f" data-agents='{agents}' data-text='{_searchable(row)}'"
    )
    out = [f"<details{attrs} class='card'><summary><div class='top'>"
           f"<span class='name'>{html.escape(name)}"
           f"<span class='kind'>{html.escape(row.get('kind') or 'unit')}</span>"
           f"{_drift_tag(a, now)}</span>"
           f"<span class='facts'>{_placed(a, now)}</span></div>"]
    for ask in a.needs[:2]:
        out.append(f"<div class='ask'>{html.escape(ask['question'].strip()[:200])}"
                   f"<span class='when'> · asked {ago(ask.get('at'), now)}</span></div>")
    if row.get("why"):
        age = f"<span class='age'>{ago(why_edited, now).replace(' ago', ' old')}{' · stale' if is_stale else ''}</span>" if why_edited else ""
        out.append(f"<div class='why{' stale' if is_stale else ''}'>&#x201C;{html.escape(row['why'])}&#x201D;{age}</div>")
    if a.notes:
        recent = ", ".join(f"<b>{html.escape(str(n['topic']))}</b>" for n in a.notes[:4])
        more = f" +{len(a.notes) - 4}" if len(a.notes) > 4 else ""
        out.append(f"<div class='notes'>{len(a.notes)} note(s): {recent}{more}</div>")
    out.append("</summary>")
    out.append(_detail(row, ctx))
    if nested:
        out.append("<div class='nested'>")
        for child in sorted(nested, key=lambda r: recency(r["activity"]), reverse=True):
            out.append(_card(child, ctx, now))
        out.append("</div>")
    out.append("</details>")
    return "".join(out)


JS = """
const chips = document.querySelectorAll('.chip');
const find = document.getElementById('find');
const on = {band: '', kind: '', agent: ''};
let q = '';
function apply() {
  document.querySelectorAll('details.card').forEach(el => {
    const kind = !on.kind || el.dataset.kind === on.kind;
    const agents = (el.dataset.agents || '').split(' ');
    const agent = !on.agent || agents.includes(on.agent);
    const text = !q || (el.dataset.text || '').includes(q);
    el.hidden = !(kind && agent && text);
  });
  document.querySelectorAll('details.band').forEach(b => {
    const mine = !on.band || b.dataset.band === on.band;
    const any = [...b.querySelectorAll(':scope > details.card')].some(c => !c.hidden);
    b.hidden = !(mine && any);
    if (on.band && mine) b.open = true;
  });
  document.querySelectorAll('.loose li').forEach(li => {
    li.hidden = !!on.agent && li.dataset.agent !== on.agent;
  });
}
chips.forEach(c => c.addEventListener('click', () => {
  const facet = c.dataset.facet;
  on[facet] = c.dataset.value;
  document.querySelectorAll(`.chip[data-facet='${facet}']`).forEach(x => x.classList.toggle('on', x === c));
  apply();
}));
find.addEventListener('input', () => { q = find.value.trim().toLowerCase(); apply(); });
document.addEventListener('click', e => {
  const c = e.target.closest('.cp'); if (!c) return; e.preventDefault();
  navigator.clipboard.writeText(c.dataset.path).then(() => {
    c.classList.add('done'); setTimeout(() => c.classList.remove('done'), 900); });
});
"""


def _chips(facet: str, values: list[tuple[str, str, int | None]], colour: bool = False) -> str:
    out = [f"<button class='chip on' data-facet='{facet}' data-value=''>all</button>"]
    for value, label, count in values:
        cls = f" {value}" if colour else ""
        n = f"<span class='n'>{count}</span>" if count is not None else ""
        out.append(f"<button class='chip{cls}' data-facet='{facet}' "
                   f"data-value='{html.escape(value, quote=True)}'>{html.escape(label)}{n}</button>")
    return "".join(out)


def render(
    groups: list[tuple[str, list[dict]]], ctx: dict, unattributed: list | None = None,
    now: float | None = None,
) -> str:
    """`groups` is [(label, [row, ...]), ...]; a row is what `cli.view` builds.
    The labels are ignored: units are banded by when they last moved, and
    their kind is a chip on the card and a filter, not a section.

    Every card folds. A unit that is part of another is a card inside its
    parent's. The page embeds every row and scopes itself in the browser.
    """
    now = time.time() if now is None else now
    rows = [r for _, group in groups for r in group]
    by_name = {r["name"]: r for r in rows}
    children: dict[str, list[dict]] = {}
    for r in rows:
        parent = r.get("part_of")
        if parent and parent in by_name:
            children.setdefault(parent, []).append(r)
    top = [r for r in rows if not (r.get("part_of") and r.get("part_of") in by_name)]

    # A parent's band is the newest of its own clocks and its parts'.
    def band_of(r: dict) -> str:
        own = band(r["activity"], now)
        kids = [band(c["activity"], now) for c in children.get(r["name"], [])]
        return min([own, *kids], key=BANDS.index)

    banded: dict[str, list[dict]] = {b: [] for b in BANDS}
    for r in top:
        banded[band_of(r)].append(r)

    running = sum(r["activity"].live_sessions for r in rows)
    waiting = sum(r["activity"].waiting for r in rows)
    kinds = sorted({r.get("kind") or "" for r in rows} - {""})

    body = [
        "<div class='filters'>"
        "<div class='facet'><span class='flabel'>when</span>"
        + _chips("band", [(b, b, len(banded[b])) for b in BANDS if banded[b]]) + "</div>"
        "<div class='facet'><span class='flabel'>kind</span>"
        + _chips("kind", [(k, k, None) for k in kinds]) + "</div>"
        "<div class='facet'><span class='flabel'>agent</span>"
        + _chips("agent", [(a, a, None) for a in ("claude", "codex", "kimi")], colour=True) + "</div>"
        "<div class='facet'><span class='flabel'>find</span>"
        "<input id='find' placeholder='unit, session, document, note…' autocomplete='off'></div>"
        "</div>"
    ]
    if running:
        body.append(f"<div class='badge live-badge'>&#x25CF; {running} running now</div> ")
    if waiting:
        body.append(f"<div class='badge'>{waiting} waiting on you</div>")
    else:
        body.append("<div class='badge clear'>nothing waiting</div>")

    for b in BANDS:
        members = banded[b]
        if not members:
            continue
        opened = " open" if b in ("waiting", "today", "yesterday") else ""
        cls = " waiting" if b == "waiting" else ""
        body.append(f"<details class='band{cls}' data-band='{b}'{opened}>"
                    f"<summary>{html.escape(b)}<span class='n'>{len(members)}</span></summary>")
        for r in sorted(members, key=lambda r: recency(r["activity"]), reverse=True):
            body.append(_card(r, ctx, now, nested=children.get(r["name"], [])))
        body.append("</details>")

    loose = listed(unattributed or [])
    if loose:
        body.append(f"<details class='band' data-band='unattributed'>"
                    f"<summary>unattributed sessions<span class='n'>{len(loose)}</span></summary>"
                    + _unattributed(loose).replace("<h2 class='grp'>", "<h2 class='grp' hidden>", 1)
                    + "</details>")

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
