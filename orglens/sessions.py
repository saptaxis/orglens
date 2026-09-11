"""Which units a session belongs to. Defined here and nowhere else.

A session belongs to a set of units. An explicit attribution — written by
`orglens start` before the first turn, or by `orglens attribute` afterwards —
names one unit, and that session belongs to it alone, whatever directory it
ran in. Without one, the session belongs to every unit that has a home
containing its working directory: one unit ordinarily, several when a home is
shared, none when it ran outside every home.

Everything that says how many sessions a unit has, or lists them, reads from
here. `activity` used to encode the same rule as a SQL clause per unit, and a
rule written twice is a rule that drifts.

The index is scad's. orglens reads it and writes nothing to it; scad does not
know orglens exists. The two file sessions under different keys — scad by the
directory a marker sits in, orglens by a declared unit spanning several
directories — and those keys are not made to match. Directory names are the
input; the unit is the output.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from orglens.events import attributions
from orglens.homes import repo_of
from orglens.units import Registry

#: scad's own words for a session that can be picked back up.
OPEN = frozenset({"awaiting-user", "awaiting-question", "in-flight"})

#: Claude writes one file per running process here. It is the only source that
#: knows a session is *live* rather than merely unfinished — the index records
#: what a trace said when it was archived, which is a different question.
#: Claude-only: codex and kimi keep no equivalent registry.
LIVE_REGISTRY = Path.home() / ".claude" / "sessions"


@dataclass(frozen=True)
class Session:
    id: str
    agent: str
    cwd: str | None
    started: int | None
    ended: int | None
    turns: int
    label: str | None
    outcome: str | None
    live: bool
    units: frozenset[str]
    #: "attributed" | "containment" | None
    how: str | None

    @property
    def open(self) -> bool:
        return self.outcome in OPEN

    @property
    def when(self) -> int | None:
        """The clock a listing sorts by: when it ended, else when it began."""
        return self.ended or self.started


def _rows(index: Path) -> list[tuple]:
    """Every main session, newest first. A missing or unreadable index is no
    sessions, not an error — the machine may simply not have scad."""
    if not index.exists():
        return []
    try:
        db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        return db.execute(
            "select id, agent, cwd, started, ended, coalesce(n_turns, 0), "
            "coalesce(nullif(name, ''), nullif(title, '')), outcome "
            "from sessions where kind = 'main' "
            "order by coalesce(ended, started) desc, id"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        db.close()


def live_now() -> dict[str, dict]:
    """session id -> {cwd, name}, for every session whose process is running.

    Liveness is a `kill(pid, 0)` against the registry. A stale file whose
    process is gone is skipped, not reported. The name is what the person
    called the session, which the index learns only on the next reindex.
    """
    out: dict[str, dict] = {}
    if not LIVE_REGISTRY.is_dir():
        return out
    for entry in sorted(LIVE_REGISTRY.glob("*.json")):
        try:
            data = json.loads(entry.read_text())
            pid = int(data["pid"])
            sid = str(data["sessionId"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        try:
            os.kill(pid, 0)
        except OSError:
            continue
        # One session can have two files — a second process attached to the
        # same id — and the newer one carries the name the person set.
        updated = data.get("updatedAt") or 0
        if sid in out and out[sid]["updated"] > updated:
            continue
        out[sid] = {"cwd": data.get("cwd"), "name": data.get("name") or None,
                    "updated": updated}
    return out


def _spellings(path: Path, roots: list[Path]) -> list[str]:
    """Every way a session might have written this path.

    The resolved form is what most sessions record. A root configured as a
    symlink — `~/Dropbox` for `~/Library/CloudStorage/Dropbox` — gives a
    second spelling that some sessions record instead, and a session is not
    less the unit's for having been started through the link.
    """
    resolved = path.resolve()
    out = [str(resolved)]
    for root in roots:
        given = Path(root).expanduser()
        real = given.resolve()
        if given != real and resolved.is_relative_to(real):
            out.append(str(given / resolved.relative_to(real)))
    return out


def _prefixes(registry: Registry) -> list[tuple[str, str]]:
    """(unit name, cwd prefix) for every home present on this machine.

    Per home: each spelling of the host path, and the container path scad
    mounts it at — a session that ran in a container records the latter.
    """
    out: list[tuple[str, str]] = []
    for unit in registry.units():
        for home in unit.homes:
            if home.path is None:
                continue
            for spelling in _spellings(home.path, registry.roots):
                out.append((unit.name, spelling))
            out.append((unit.name, f"/workspace/{repo_of(home.name)}"))
    return out


def _under(cwd: str, prefix: str) -> bool:
    return cwd == prefix or cwd.startswith(prefix.rstrip("/") + "/")


def all_sessions(registry: Registry, index: Path, events_root: Path) -> list[Session]:
    """Every session scad knows about, plus any running now that the index
    has not caught up with, each with the units it belongs to.

    Zero-turn rows are included: a session scad indexed at launch has none
    until its first turn lands, and it is exactly the one that is live. A
    listing hides them; a count and a live check must not.
    """
    attributed = attributions(root=events_root)
    prefixes = _prefixes(registry)
    live = live_now()

    def belongs(sid: str, cwd: str | None) -> tuple[frozenset[str], str | None]:
        if sid in attributed:
            return frozenset({attributed[sid]}), "attributed"
        units = frozenset(name for name, prefix in prefixes if cwd and _under(cwd, prefix))
        return units, ("containment" if units else None)

    out: list[Session] = []
    seen: set[str] = set()
    for sid, agent, cwd, started, ended, turns, label, outcome in _rows(index):
        seen.add(sid)
        units, how = belongs(sid, cwd)
        out.append(Session(
            id=sid, agent=agent, cwd=cwd, started=started, ended=ended,
            turns=turns, label=label or live.get(sid, {}).get("name"),
            outcome=outcome, live=sid in live, units=units, how=how,
        ))
    # Running, in the registry, not yet indexed: a session started by hand
    # reaches the index on the next reindex, and it is the unit's now.
    for sid, entry in live.items():
        if sid in seen:
            continue
        units, how = belongs(sid, entry["cwd"])
        out.append(Session(
            id=sid, agent="claude", cwd=entry["cwd"], started=None, ended=None,
            turns=0, label=entry["name"], outcome=None, live=True,
            units=units, how=how,
        ))
    return out


def for_unit(sessions: list[Session], name: str) -> list[Session]:
    return [s for s in sessions if name in s.units]


def unattributed(sessions: list[Session]) -> list[Session]:
    return [s for s in sessions if not s.units]


def listed(sessions: list[Session], everything: bool = False) -> list[Session]:
    """What a listing shows, in the order it shows it.

    Running first: a just-launched session has no clock yet, and it is the
    one you most want to see. Without `everything`, the rows scad indexed
    at launch that have no turn yet are left out, unless they are running.
    """
    shown = [s for s in sessions if everything or s.turns or s.live]
    return sorted(shown, key=lambda s: (s.live, s.when or 0, s.id), reverse=True)
