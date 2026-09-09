"""What is true about an entity right now, derived rather than declared.

An entity's `overview.md` carries a hand-written status line. It drifts, because
nothing forces anyone to update it: orglens' own said "v1 core implemented"
while plan 07 was merged. That is a stored status field — the shape the workflow
face refuses outright, where `runs.jsonl` rejects the keys `status`, `state`,
`pending`, `current_state` and `next_node` for exactly this reason.

So the position is computed and only the reasoning stays written down. A
sentence that says *"the draft is dead pending a literature refresh"* is a
judgement no scan reconstructs and belongs in the doc; a sentence that says
*"v1 core implemented"* is a progress claim the tree already answers.

Four sources, none of which reads a document body:

    git         when the directory was last committed to, and what is unstaged
    filenames   the highest-numbered plan
    runs.jsonl  workflow packets, and which are waiting on a human
    scad index  sessions attributed to this entity, and their open questions

Every one degrades to empty rather than raising: a tree outside git, a machine
without scad, an entity with no plans are all ordinary.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path

SCAD_INDEX = Path.home() / ".scad" / "index.sqlite"

#: Claude writes one file per running process here. It is the only source that
#: knows a session is *live* rather than merely unfinished — the index records
#: what a trace said when it was archived, which is a different question.
LIVE_REGISTRY = Path.home() / ".claude" / "sessions"


@dataclass
class Activity:
    touched: int | None = None          # epoch seconds of the last commit
    modified: int | None = None         # newest file mtime — edits not yet landed
    dirty: int = 0                      # uncommitted paths beneath the entity
    plan: str | None = None             # highest-numbered plan, e.g. "07"
    packets: int = 0
    blocked: int = 0                    # packets holding an unanswered question
    sessions: int = 0
    last_session: int | None = None     # epoch seconds
    turns: int = 0
    last_turn: dict | None = None       # {at, role, text} — what was last said
    recent: list[dict] = field(default_factory=list)  # last few main sessions
    live: list[dict] = field(default_factory=list)     # processes running now
    agents: list[str] = field(default_factory=list)
    needs: list[dict] = field(default_factory=list)   # {question, at}
    notes: list[dict] = field(default_factory=list)   # the authored tier

    @property
    def live_sessions(self) -> int:
        """Panes you could switch to right now."""
        return len(self.live)

    @property
    def open_sessions(self) -> int:
        """Sessions that stopped mid-conversation — the resumable ones."""
        return sum(1 for s in self.recent if s["open"])

    @property
    def waiting(self) -> int:
        """Everything that cannot proceed without the human."""
        return self.blocked + len(self.needs)


def recency(a: Activity) -> int:
    """Latest wins, across two independent clocks.

    A tree edited an hour ago and a session that ran last week are both "recent"
    for different reasons, and either can be the one you meant. `list`,
    `status` and the HTML view all order units by this, so it lives here once
    rather than being re-decided by each caller.
    """
    if a.live:
        return 1 << 62          # running now — nothing outranks it
    spoke = (a.last_turn or {}).get("at") or a.last_session or 0
    return max(a.modified or 0, spoke)


def _git(args: list[str], cwd: Path) -> str:
    try:
        r = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
        )
    except OSError:
        return ""
    return r.stdout if r.returncode == 0 else ""


def _repo_root(path: Path) -> Path | None:
    out = _git(["rev-parse", "--show-toplevel"], path)
    return Path(out.strip()) if out.strip() else None


def _last_commit(root: Path, path: Path) -> int | None:
    out = _git(["log", "-1", "--format=%ct", "--", str(path)], root).strip()
    return int(out) if out.isdigit() else None


def _dirty(root: Path, path: Path) -> int:
    out = _git(["status", "--porcelain", "--", str(path)], root)
    return sum(1 for line in out.splitlines() if line.strip())


_SKIP = {".git", "node_modules", "__pycache__", ".venv"}


def _newest_mtime(path: Path) -> int | None:
    """When the tree was last edited, landed or not.

    The last commit says what was published; this says what was touched. They
    diverge exactly when work is in flight, which is when you care.
    """
    newest = 0
    stack = [path]
    while stack:
        try:
            entries = list(stack.pop().iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.name.startswith(".") or entry.name in _SKIP:
                continue
            try:
                if entry.is_dir():
                    stack.append(entry)
                else:
                    newest = max(newest, int(entry.stat().st_mtime))
            except OSError:
                continue
    return newest or None


def _latest_plan(path: Path) -> str | None:
    """The highest-numbered plan, by filename. No file is opened."""
    plans = sorted((path / "plans").glob("[0-9][0-9]-*.md"))
    return plans[-1].name[:2] if plans else None


def _packets(path: Path) -> tuple[int, int]:
    """Workflow packets beneath the entity, and how many hold a question."""
    from orglens.workflow.runstate import read_entries, unresolved_needs_human

    total = blocked = 0
    for log in path.rglob("runs.jsonl"):
        total += 1
        try:
            if unresolved_needs_human(read_entries(log.parent)) is not None:
                blocked += 1
        except (ValueError, OSError):
            pass
    return total, blocked


@lru_cache(maxsize=1)
def _live_entries(index: Path) -> list[dict]:
    """Every session whose process is still running right now, unfiled by
    project — grouping by scad's `project` column is exactly the coincidence
    this module exists to delete. `_live_for` does the actual filing, by cwd.

    Liveness is a `kill(pid, 0)` against the registry Claude maintains.
    Claude-only — codex and kimi keep no equivalent registry, so their live
    work is invisible here.
    """
    out: list[dict] = []
    if not LIVE_REGISTRY.is_dir():
        return out
    db = None
    if index.exists():
        try:
            db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
        except sqlite3.Error:
            db = None
    for entry in sorted(LIVE_REGISTRY.glob("*.json")):
        try:
            data = json.loads(entry.read_text())
            pid = int(data["pid"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        try:
            os.kill(pid, 0)
        except OSError:
            continue
        label = None
        if db is not None:
            row = db.execute(
                "select coalesce(nullif(name,''), nullif(title,'')) "
                "from sessions where id = ?",
                (data.get("sessionId"),),
            ).fetchone()
            label = row[0] if row else None
        out.append(
            {
                "pid": pid,
                "session": data.get("sessionId"),
                "cwd": data.get("cwd"),
                "kind": data.get("kind"),
                "name": label,
            }
        )
    if db is not None:
        db.close()
    return out


def _live_for(paths: list[Path], home_names: list[str], index: Path) -> list[dict]:
    """Live sessions whose cwd is under one of this unit's homes.

    Matches by cwd, the same evidence `_sessions` joins on — not scad's
    `project` column, which is the exact coincidence this branch exists to
    delete. A live session running in a unit's docs home used to be filed
    under the docs repository's own project name and never show as running
    against the unit at all.
    """
    resolved = [str(Path(p).resolve()) for p in paths]
    containers = [f"/workspace/{name.split('/')[0]}" for name in home_names]

    def under(cwd: str, prefixes: list[str]) -> bool:
        return any(cwd == p or cwd.startswith(p + "/") for p in prefixes)

    return [
        entry
        for entry in _live_entries(index)
        if entry.get("cwd")
        and (under(entry["cwd"], resolved) or under(entry["cwd"], containers))
    ]


def _epoch(ts) -> int | None:
    """scad writes note timestamps as ISO strings; the view wants seconds."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return int(ts) // (1000 if ts > 1e11 else 1)
    try:
        return int(datetime.fromisoformat(str(ts)).timestamp())
    except ValueError:
        return None


def _json_list(raw: str | None) -> list[str]:
    """scad stores tags and entities as JSON arrays of strings."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return [str(v) for v in value] if isinstance(value, list) else []


#: Outcomes that mean the conversation stopped without finishing — the ones
#: you can pick back up. scad's own viewer treats the first two the same way.
_OPEN = {"awaiting-user", "awaiting-question", "in-flight"}

_EMPTY: tuple = (0, None, 0, None, [], [], [], [])


def _home_clause(paths: list[Path], names: list[str]) -> tuple[str, list[str]]:
    """SQL matching sessions that ran in, or under, any of these homes.

    The join used to be `where project = <entity name>`, which worked only
    while a repository happened to be named after the work. neuronal-degeneracy
    is one unit with 1,281 sessions that split into two buckets under that
    rule — 682 under its own name, 599 under `traitful-docs`.

    Paths are resolved because `~/Dropbox` is a symlink to
    `~/Library/CloudStorage/Dropbox` and 1,547 of 1,667 sessions record the
    resolved form. An unresolved home matches nothing, and says so by
    reporting zero rather than by failing.

    Container paths are matched by name because a dispatched session's cwd is
    `/workspace/<repo>`, which no host path can match — 37 sessions, 35 of
    them orglens's own. That is scad's mounting convention, not a guess.
    """
    clauses: list[str] = []
    params: list[str] = []
    for path in paths:
        resolved = str(Path(path).resolve())
        clauses.append("(cwd = ? or cwd like ?)")
        params += [resolved, resolved + "/%"]
    for name in names:
        repo = name.split("/")[0]
        clauses.append("(cwd = ? or cwd like ?)")
        params += [f"/workspace/{repo}", f"/workspace/{repo}/%"]
    if not clauses:
        return "0", []
    return "(" + " or ".join(clauses) + ")", params


def _sessions(
    paths: list[Path], name: str, index: Path, home_names: list[str] | None = None
) -> tuple:
    """Sessions scad attributed to this unit, and their open questions."""
    if not index.exists():
        return _EMPTY
    try:
        db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    except sqlite3.Error:
        return _EMPTY
    try:
        clause, params = _home_clause(paths, home_names or [])
        count, last, turns = db.execute(
            "select count(*), max(coalesce(ended, started)), "
            f"sum(coalesce(n_turns, 0)) from sessions where {clause}",
            params,
        ).fetchone()
        agents = [
            row[0]
            for row in db.execute(
                f"select distinct agent from sessions where {clause} "
                "and agent is not null order by agent",
                params,
            )
        ]
        # A note is *about* an entity, which is not the same as being *written
        # in* one. The field report on orglens was authored from a session in
        # another project and cross-tagged; joining on the session's project
        # alone found three of the eight notes that actually discuss orglens.
        # The table is small, so match exactly in Python rather than with LIKE
        # over JSON text.
        # The exact last turn, not just when the session ended. It carries what
        # was actually said, which answers "what was I doing" in a way no count
        # does. Costs a few hundred ms across the whole tree — the render
        # already spends more than that in git.
        row = db.execute(
            "select t.ts, t.role, substr(t.text, 1, 240) from turns t "
            "join sessions s on s.id = t.session_id "
            f"where {clause} and t.text is not null and t.text != '' "
            "order by t.ts desc limit 1",
            params,
        ).fetchone()
        last_turn = (
            {"at": _epoch(row[0]), "role": row[1], "text": row[2]} if row else None
        )

        # Only `main` sessions. The store is 1264 workflow-agents against 232
        # mains, and a subagent is an implementation detail of a session that
        # is already listed.
        recent = [
            {
                "at": _epoch(at),
                "agent": agent,
                "outcome": outcome,
                "name": row_name or title,
                "turns": n_turns or 0,
                "open": outcome in _OPEN,
            }
            for at, agent, outcome, row_name, title, n_turns in db.execute(
                "select coalesce(ended, started), agent, outcome, name, title, "
                f"n_turns from sessions where {clause} and kind = 'main' "
                "order by coalesce(ended, started) desc limit 8",
                params,
            )
        ]

        notes = []
        for topic, title, ts, tags, entities, project in db.execute(
            "select n.topic, n.title, n.ts, n.tags, n.entities, s.project "
            "from notes n join sessions s on s.id = n.session_id order by n.ts desc"
        ):
            named = name in _json_list(tags) or name in _json_list(entities)
            if not (named or topic == name or project == name):
                continue
            notes.append(
                {
                    "topic": topic,
                    "title": title,
                    "at": _epoch(ts),
                    "written_in": project,
                    "about": named or topic == name,
                }
            )
        # `ended` is when the session stopped with the question outstanding,
        # which is the date a human actually cares about — how long it has sat.
        needs = [
            {"question": q, "at": (int(at) // 1000 if at else None)}
            for q, at in db.execute(
                "select needs, coalesce(ended, started) from sessions "
                f"where {clause} and needs is not null and needs != '' "
                "order by coalesce(ended, started) desc",
                params,
            )
        ]
    except sqlite3.Error:
        return _EMPTY
    finally:
        db.close()
    # scad stores epoch milliseconds.
    return (
        count or 0,
        (int(last) // 1000 if last else None),
        turns or 0,
        last_turn,
        recent,
        agents,
        needs,
        notes,
    )


def _session_clock(
    paths: list[Path], index: Path, home_names: list[str]
) -> tuple[int, int | None]:
    """Count and last-active time — measured against the real scad index (not
    a synthetic one) to matter here. A first cut also joined `turns` for the
    exact last-said text, mirroring `_sessions`; on this machine's index
    (74k turns, no index on `session_id` or `ts`) that one join cost 1.6s
    across 16 units — 85% of `peek`'s entire time and enough on its own to
    erase the git-subprocess saving this function exists for. `sessions.ended`
    already answers "when did a session last touch this unit" without it.
    """
    if not index.exists():
        return 0, None
    try:
        db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    except sqlite3.Error:
        return 0, None
    try:
        clause, params = _home_clause(paths, home_names or [])
        count, last = db.execute(
            f"select count(*), max(coalesce(ended, started)) from sessions "
            f"where {clause}",
            params,
        ).fetchone()
    except sqlite3.Error:
        return 0, None
    finally:
        db.close()
    return count or 0, (int(last) // 1000 if last else None)


def peek(
    paths: list[Path],
    name: str,
    index: Path = SCAD_INDEX,
    home_names: list[str] | None = None,
) -> Activity:
    """Just enough to sort and date a unit — what `list` needs, not what
    `status` shows in full.

    Two costs stand between `list` and `read`'s full picture: the git
    subprocess `read` runs per home for the last commit and the dirty count
    (the plan/packet file walks are cheap by comparison), and — measured,
    not assumed — the `turns` join `_sessions` uses for the exact last-said
    text, which dwarfs it on a real index. Ordering and dating a unit needs
    neither: the newest file mtime and `sessions.ended` are enough, so this
    skips both rather than pay for what nothing here displays.
    """
    paths = [Path(p) for p in paths]
    home_names = home_names or []
    a = Activity()
    if not paths:
        return a
    a.modified = max((_newest_mtime(p) or 0) for p in paths) or None
    a.live = _live_for(paths, home_names, index)
    a.sessions, a.last_session = _session_clock(paths, index, home_names)
    return a


def read(
    paths: list[Path],
    name: str,
    index: Path = SCAD_INDEX,
    home_names: list[str] | None = None,
) -> Activity:
    """Everything derivable about one unit. Never raises."""
    paths = [Path(p) for p in paths]
    home_names = home_names or []
    activity = Activity()
    if not paths:
        return activity

    # Every fact below spans every home, not only `paths[0]`. A unit whose
    # docs home happened to be listed first used to report the docs home's
    # commit date, its plan count and nothing else — missing the code home's
    # workflow packets and its more recent commits entirely.
    roots = [(p, _repo_root(p)) for p in paths]
    commits = [
        c for p, r in roots if r and (c := _last_commit(r, p)) is not None
    ]
    activity.touched = max(commits) if commits else None
    activity.dirty = sum(_dirty(r or p, p) for p, r in roots)
    activity.modified = max((_newest_mtime(p) or 0) for p in paths) or None

    activity.live = _live_for(paths, home_names, index)
    plans = [p for path in paths if (p := _latest_plan(path)) is not None]
    activity.plan = max(plans) if plans else None
    packets = [_packets(p) for p in paths]
    activity.packets = sum(total for total, _ in packets)
    activity.blocked = sum(blocked for _, blocked in packets)
    (
        activity.sessions,
        activity.last_session,
        activity.turns,
        activity.last_turn,
        activity.recent,
        activity.agents,
        activity.needs,
        activity.notes,
    ) = _sessions(paths, name, index, home_names)
    return activity
