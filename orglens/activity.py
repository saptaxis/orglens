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
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

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
    agents: list[str] = field(default_factory=list)
    needs: list[dict] = field(default_factory=list)   # {question, at}
    notes: list[dict] = field(default_factory=list)   # the authored tier

    @property
    def open_sessions(self) -> int:
        """Sessions that stopped mid-conversation — the resumable ones."""
        return sum(1 for s in self.recent if s["open"])

    @property
    def waiting(self) -> int:
        """Everything that cannot proceed without the human."""
        return self.blocked + len(self.needs)


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


def _sessions(name: str, index: Path) -> tuple:
    """Sessions scad attributed to this entity, and their open questions."""
    if not index.exists():
        return _EMPTY
    try:
        db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    except sqlite3.Error:
        return _EMPTY
    try:
        count, last, turns = db.execute(
            "select count(*), max(coalesce(ended, started)), "
            "sum(coalesce(n_turns, 0)) from sessions where project = ?",
            (name,),
        ).fetchone()
        agents = [
            row[0]
            for row in db.execute(
                "select distinct agent from sessions where project = ? "
                "and agent is not null order by agent",
                (name,),
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
            "where s.project = ? and t.text is not null and t.text != '' "
            "order by t.ts desc limit 1",
            (name,),
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
                "name": name or title,
                "turns": n_turns or 0,
                "open": outcome in _OPEN,
            }
            for at, agent, outcome, name, title, n_turns in db.execute(
                "select coalesce(ended, started), agent, outcome, name, title, "
                "n_turns from sessions where project = ? and kind = 'main' "
                "order by coalesce(ended, started) desc limit 8",
                (name,),
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
                "where project = ? and needs is not null and needs != '' "
                "order by coalesce(ended, started) desc",
                (name,),
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


def read(path: Path, name: str, index: Path = SCAD_INDEX) -> Activity:
    """Everything derivable about one entity. Never raises."""
    path = Path(path)
    activity = Activity()

    root = _repo_root(path)
    if root is not None:
        activity.touched = _last_commit(root, path)
        activity.dirty = _dirty(root, path)
    activity.modified = _newest_mtime(path)

    activity.plan = _latest_plan(path)
    activity.packets, activity.blocked = _packets(path)
    (
        activity.sessions,
        activity.last_session,
        activity.turns,
        activity.last_turn,
        activity.recent,
        activity.agents,
        activity.needs,
        activity.notes,
    ) = _sessions(name, index)
    return activity
