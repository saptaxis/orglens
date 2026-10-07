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
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from orglens import skip
from orglens import sessions as sessions_mod
from orglens.sessions import Session




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
    memos: list[dict] = field(default_factory=list)   # the authored tier

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
    """The repository holding `path`: the nearest ancestor with a `.git`.

    A directory or a file — a worktree's `.git` is a file naming the real
    one. Walked in Python rather than asked of git: `rev-parse` per home
    was sixty subprocesses per `status`.
    """
    here = Path(path).resolve()
    for directory in (here, *here.parents):
        if (directory / ".git").exists():
            return directory
    return None


@lru_cache(maxsize=None)
def _last_commit(root: Path, path: Path) -> int | None:
    """When `path` last landed in `root`. Cached per process: a home is asked
    for by `status` and again by the status line's `_last_edit`."""
    out = _git(["log", "-1", "--format=%ct", "--", str(path)], root).strip()
    return int(out) if out.isdigit() else None


def prefetch(paths: list[Path], extra: list[tuple] = (), workers: int = 8) -> None:
    """Warm the per-path git answers for every path at once.

    `_last_commit` is one subprocess per home and per driver document —
    ninety in series on a 25-unit tree, 2.5s of a 5s `view`. They do not
    depend on each other, so a small pool runs them side by side and the
    per-unit loop afterwards finds every answer cached. `extra` is more
    (function, argument) pairs to run in the same pool — the memos fetch,
    one scad subprocess.
    """
    from concurrent.futures import ThreadPoolExecutor

    def one(path: Path) -> None:
        root = _repo_root(path)
        if root is not None:
            _last_commit(root, Path(path))
            _status_lines(root)

    def walk(path: Path) -> None:
        _newest_mtime(Path(path))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, p) for p in paths]
        futures += [pool.submit(walk, p) for p in paths if Path(p).is_dir()]
        futures += [pool.submit(fn, arg) for fn, arg in extra]
        for f in futures:
            f.result()


@lru_cache(maxsize=None)
def _status_lines(root: Path) -> tuple[str, ...]:
    """`git status --porcelain` for a whole repository, once per process.

    Several homes sit in one repository, and each used to run its own
    status. The paths come back repository-relative.
    """
    out = _git(["status", "--porcelain", "--untracked-files=all"], root)
    return tuple(line for line in out.splitlines() if line.strip())


def _dirty(root: Path, path: Path) -> int:
    """Uncommitted paths under `path`, from the repository's one status."""
    try:
        rel = Path(path).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return 0
    prefix = "" if str(rel) == "." else str(rel).rstrip("/") + "/"
    count = 0
    for line in _status_lines(Path(root).resolve()):
        # Porcelain: two status columns, a space, then the path; a rename
        # is `old -> new` and the new path is what exists.
        entry = line[3:].split(" -> ")[-1].strip('"')
        if entry.startswith(prefix):
            count += 1
    return count


@lru_cache(maxsize=None)
def _newest_mtime(path: Path) -> int | None:
    """When the tree was last edited, landed or not. Cached per process and
    warmed by `prefetch`; it is a full file walk of the home.

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
            if skip.skipped(entry.name):
                continue
            try:
                if entry.is_dir():
                    if skip.descend(entry):
                        stack.append(entry)
                else:
                    newest = max(newest, int(entry.stat().st_mtime))
            except OSError:
                continue
    return newest or None


def _latest_plan(path: Path) -> str | None:
    """The highest-numbered plan, by filename, in any format. No file is opened."""
    from orglens import formats
    plans = sorted(p for p in (path / "plans").glob("[0-9][0-9]-*")
                   if formats.is_document(p))
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
    """scad writes memo timestamps as ISO strings; the view wants seconds."""
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


#: How a memo reached a unit, strongest first. `written here` is the only
#: one that is exact: it is the unit the memo's own session belongs to.
WRITTEN, FILED, MENTIONS = "written here", "filed here", "mentions this"


def all_memos(limit: int = 2000) -> list[dict]:
    """Every memo scad has, newest first, in one call. Raises `ScadFailed`
    when scad refuses, as it does until a machine's memo store is moved.

    One subprocess for the whole tree rather than one per unit: `--about
    NAME` answered a single unit, so a 31-unit tree paid 31 launches to
    read the same file. The export carries `session_id`, `entities`,
    `tags` and `project`, which is everything the join below needs.
    """
    return sessions_mod.run_scad_or_say(["memos", "ls", "--limit", str(limit)])


def _mentions(memo: dict, name: str) -> bool:
    """scad's own `--about` rule, applied here: the name is in the tags or
    the entities, or it is the topic."""
    if memo.get("topic") == name:
        return True
    named = _json_list_or_list(memo.get("tags")) + _json_list_or_list(memo.get("entities"))
    return name in named


def _shape(memo: dict, how: str) -> dict:
    return {
        "topic": memo.get("topic"),
        "title": memo.get("title"),
        "at": _epoch(memo.get("ts")),
        "written_in": memo.get("project"),
        "session": memo.get("session_id"),
        "how": how,
        # Kept for callers that predate `how`: true unless the only reason
        # this memo reached the unit was the session it was written in.
        "about": how != WRITTEN or _mentions(memo, memo.get("project") or ""),
    }


def memos_by_unit(names, sessions: list[Session] | None = None,
                  memos: list[dict] | None = None) -> dict[str, list[dict]]:
    """Every named unit's memos, from one read of scad's export.

    Three ways a memo reaches a unit, and the strongest wins. **Written
    here** is the exact one: the memo's session belongs to the unit, by
    attribution or by containment — the same rule `sessions` already
    decides, and the only one that does not depend on someone having
    tagged the memo. **Filed here** is scad's project for it, which is a
    directory name and so answers only for the units whose name is their
    repository's. **Mentions this** is the old `--about` match, kept as a
    weaker source rather than the only one.

    Passing `sessions` is what makes the first rule work; without it this
    degrades to what `--about` did.
    """
    names = list(names)
    rows = all_memos() if memos is None else memos
    by_session: dict[str, frozenset[str]] = {
        s.id: s.units for s in (sessions or []) if s.units
    }
    out: dict[str, list[dict]] = {name: [] for name in names}
    wanted = set(names)
    for memo in rows:
        written = by_session.get(str(memo.get("session_id") or "")) or frozenset()
        filed = memo.get("project")
        for name in wanted:
            if name in written:
                out[name].append(_shape(memo, WRITTEN))
            elif name == filed:
                out[name].append(_shape(memo, FILED))
            elif _mentions(memo, name):
                out[name].append(_shape(memo, MENTIONS))
    return out


def memos_about(name: str, sessions: list[Session] | None = None,
                memos: list[dict] | None = None) -> list[dict]:
    """One unit's memos. See `memos_by_unit`, which this is a slice of."""
    return memos_by_unit([name], sessions, memos)[name]


def _json_list_or_list(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(v) for v in raw]
    return _json_list(raw)


def _from_sessions(sessions: list[Session]) -> dict:
    """The facts the `Session` list already carries, in `Activity`'s shape.
    scad stores epoch milliseconds; `Activity` speaks seconds."""
    newest = sorted(sessions, key=lambda s: (s.when or 0, s.id), reverse=True)
    last = max((s.when or 0 for s in sessions), default=0)
    # The exact last turn, not just when the session ended. It carries what
    # was actually said, which answers "what was I doing" in a way no count
    # does. scad clips the text; the newest across the unit's sessions wins.
    turns_said = [s.last_turn for s in sessions if s.last_turn and s.last_turn.get("text")]
    said = max(turns_said, key=lambda t: _epoch(t.get("ts")) or 0, default=None)
    return {
        "sessions": len(sessions),
        "last_session": (last // 1000) if last else None,
        "turns": sum(s.turns for s in sessions),
        "agents": sorted({s.agent for s in sessions if s.agent}),
        "last_turn": (
            {"at": _epoch(said.get("ts")), "role": said.get("role"), "text": said.get("text")}
            if said else None
        ),
        # `ended` is when the session stopped with the question outstanding,
        # which is the date a human actually cares about — how long it has sat.
        "needs": [
            {"question": s.needs, "at": (s.when // 1000) if s.when else None}
            for s in newest if s.needs
        ],
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
        # `spoke` is when the session last said anything; a pane that is
        # open but has not spoken for a day is idle, not work in progress.
        "live": [
            {"session": s.id, "name": s.label, "cwd": s.cwd,
             "spoke": _epoch((s.last_turn or {}).get("ts")) or ((s.when // 1000) if s.when else None)}
            for s in newest if s.live
        ],
    }


def peek(
    paths: list[Path],
    name: str,
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
    sessions: list[Session] | None = None,
    memos: list[dict] | None = None,
) -> Activity:
    """Everything derivable about one unit. Never raises.

    `sessions` is the unit's, decided by `sessions.for_unit`; nothing here
    asks which sessions belong. None given means none. `memos` is what
    `memos_about` returns, passed in when the caller fetched it already.
    """
    paths = [Path(p) for p in paths]
    sessions = sessions or []
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
    # The session join needs the unit's sessions, which are in hand here.
    if memos is None:
        try:
            memos = memos_about(name, sessions)
        except sessions_mod.ScadFailed:
            # The commands that show memos say why; this one never raises.
            memos = []
    activity.memos = memos
    return activity
