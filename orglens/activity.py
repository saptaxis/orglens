"""What is true about an entity right now, derived rather than declared.

An entity's `overview.md` carries a hand-written status line. It drifts, because
nothing forces anyone to update it: orglens' own said "v1 core implemented"
while plan 07 was merged. That is a stored status field — the shape the workflow
engine refuses outright: a packet's `session.jsonl` holds facts about the past
and its position is derived from them, never written down.

So the position is computed and only the reasoning stays written down. A
sentence that says *"the draft is dead pending a literature refresh"* is a
judgement no scan reconstructs and belongs in the doc; a sentence that says
*"v1 core implemented"* is a progress claim the tree already answers.

Four sources, none of which reads a document body:

    git         when the directory was last committed to, and what is unstaged
    filenames   the highest-numbered plan
    session.jsonl  workflow packets, and which are waiting on a human
    scad index  sessions attributed to this entity, and their open questions

Every one degrades to empty rather than raising: a tree outside git, a machine
without scad, an entity with no plans are all ordinary.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from orglens.sessions import Session

SCAD_INDEX = Path.home() / ".scad" / "index.sqlite"



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
    """Workflow packets beneath the entity, and how many are waiting on a human.

    A packet is a directory holding a `session.jsonl`. The workflow is loaded
    when it can be, so `review` gates count; where it cannot — not checked
    out on this machine — only a `done` with a question counts.
    """
    from orglens.workflow import session
    from orglens.workflow.definition import WorkflowError, load_workflow

    total = blocked = 0
    for found in path.rglob(session.SESSION_FILE):
        total += 1
        facts = session.read(found.parent)
        bound = session.workflow_path(facts)
        workflow = None
        if bound is not None:
            try:
                workflow = load_workflow(bound)
            except WorkflowError:
                workflow = None
        if session.gated(facts, workflow):
            blocked += 1
    return total, blocked


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


_NOTHING: tuple = (None, [], [])


def _from_index(ids: list[str], name: str, index: Path) -> tuple:
    """What the index holds about these sessions that `Session` does not
    carry: the last thing said, open questions, and the notes about the unit.

    Which sessions are the unit's was decided before this was called. The
    queries take the ids and nothing else; no cwd is matched here.
    """
    if not ids or not index.exists():
        return _NOTHING
    try:
        db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    except sqlite3.Error:
        return _NOTHING
    marks = ", ".join("?" * len(ids))
    try:
        # The exact last turn, not just when the session ended. It carries what
        # was actually said, which answers "what was I doing" in a way no count
        # does.
        row = db.execute(
            "select ts, role, substr(text, 1, 240) from turns "
            f"where session_id in ({marks}) and text is not null and text != '' "
            "order by ts desc limit 1",
            ids,
        ).fetchone()
        last_turn = (
            {"at": _epoch(row[0]), "role": row[1], "text": row[2]} if row else None
        )
        # `ended` is when the session stopped with the question outstanding,
        # which is the date a human actually cares about — how long it has sat.
        needs = [
            {"question": q, "at": (int(at) // 1000 if at else None)}
            for q, at in db.execute(
                "select needs, coalesce(ended, started) from sessions "
                f"where id in ({marks}) and needs is not null and needs != '' "
                "order by coalesce(ended, started) desc",
                ids,
            )
        ]
        # A note is *about* an entity, which is not the same as being *written
        # in* one. The field report on orglens was authored from a session in
        # another project and cross-tagged; joining on the session's project
        # alone found three of the eight notes that actually discuss orglens.
        # The table is small, so match exactly in Python rather than with LIKE
        # over JSON text.
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
    except sqlite3.Error:
        return _NOTHING
    finally:
        db.close()
    return last_turn, needs, notes


def _from_sessions(sessions: list[Session]) -> dict:
    """The facts the `Session` list already carries, in `Activity`'s shape.
    scad stores epoch milliseconds; `Activity` speaks seconds."""
    newest = sorted(sessions, key=lambda s: (s.when or 0, s.id), reverse=True)
    last = max((s.when or 0 for s in sessions), default=0)
    return {
        "sessions": len(sessions),
        "last_session": (last // 1000) if last else None,
        "turns": sum(s.turns for s in sessions),
        "agents": sorted({s.agent for s in sessions if s.agent}),
        # The recent few, main sessions only — a `Session` already is one.
        "recent": [
            {
                "id": s.id,
                "at": (s.when // 1000) if s.when else None,
                "agent": s.agent,
                "outcome": s.outcome,
                "name": s.label,
                "turns": s.turns,
                "open": s.open,
                "how": s.how,
            }
            for s in newest[:8]
        ],
        "live": [
            {"session": s.id, "name": s.label, "cwd": s.cwd}
            for s in newest if s.live
        ],
    }


def peek(
    paths: list[Path],
    name: str,
    index: Path | None = None,
    sessions: list[Session] | None = None,
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

    `attributed` must reach the same session count `read` reports, or `list`
    and `status` disagree about the same unit — an explicitly attributed
    session outside every home would show up in one and not the other.
    """
    paths = [Path(p) for p in paths]
    a = Activity()
    if not paths:
        return a
    a.modified = max((_newest_mtime(p) or 0) for p in paths) or None
    facts = _from_sessions(sessions or [])
    a.sessions, a.last_session, a.live = facts["sessions"], facts["last_session"], facts["live"]
    return a


def read(
    paths: list[Path],
    name: str,
    index: Path | None = None,
    sessions: list[Session] | None = None,
) -> Activity:
    """Everything derivable about one unit. Never raises.

    `sessions` is the unit's, decided by `sessions.for_unit`; nothing here
    asks which sessions belong. None given means none.
    """
    paths = [Path(p) for p in paths]
    sessions = sessions or []
    # Resolved here, not in the signature: a default argument is bound at
    # import, and `SCAD_INDEX` is what a test reassigns to keep the real
    # `~/.scad` out of the suite.
    index = SCAD_INDEX if index is None else index
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

    plans = [p for path in paths if (p := _latest_plan(path)) is not None]
    activity.plan = max(plans) if plans else None
    packets = [_packets(p) for p in paths]
    activity.packets = sum(total for total, _ in packets)
    activity.blocked = sum(blocked for _, blocked in packets)
    for key, value in _from_sessions(sessions).items():
        setattr(activity, key, value)
    activity.last_turn, activity.needs, activity.notes = _from_index(
        [s.id for s in sessions], name, index
    )
    return activity
