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

import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

SCAD_INDEX = Path.home() / ".scad" / "index.sqlite"


@dataclass
class Activity:
    touched: int | None = None          # epoch seconds of the last commit
    dirty: int = 0                      # uncommitted paths beneath the entity
    plan: str | None = None             # highest-numbered plan, e.g. "07"
    packets: int = 0
    blocked: int = 0                    # packets holding an unanswered question
    sessions: int = 0
    last_session: int | None = None     # epoch seconds
    needs: list[str] = field(default_factory=list)

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


def _sessions(name: str, index: Path) -> tuple[int, int | None, list[str]]:
    """Sessions scad attributed to this entity, and their open questions."""
    if not index.exists():
        return 0, None, []
    try:
        db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    except sqlite3.Error:
        return 0, None, []
    try:
        count, last = db.execute(
            "select count(*), max(started) from sessions where project = ?", (name,)
        ).fetchone()
        needs = [
            row[0]
            for row in db.execute(
                "select needs from sessions where project = ? "
                "and needs is not null and needs != '' order by started desc",
                (name,),
            )
        ]
    except sqlite3.Error:
        return 0, None, []
    finally:
        db.close()
    # scad stores epoch milliseconds.
    return count or 0, (int(last) // 1000 if last else None), needs


def read(path: Path, name: str, index: Path = SCAD_INDEX) -> Activity:
    """Everything derivable about one entity. Never raises."""
    path = Path(path)
    activity = Activity()

    root = _repo_root(path)
    if root is not None:
        activity.touched = _last_commit(root, path)
        activity.dirty = _dirty(root, path)

    activity.plan = _latest_plan(path)
    activity.packets, activity.blocked = _packets(path)
    activity.sessions, activity.last_session, activity.needs = _sessions(name, index)
    return activity
