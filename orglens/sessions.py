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

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from orglens.events import attributions
from orglens.homes import repo_of
from orglens.units import Registry

#: scad's own words for a session that can be picked back up.
OPEN = frozenset({"awaiting-user", "awaiting-question", "in-flight"})


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


def _rows(index: Path, include_empty: bool) -> list[tuple]:
    """Every main session, newest first. A missing or unreadable index is no
    sessions, not an error — the machine may simply not have scad."""
    if not index.exists():
        return []
    try:
        db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        turns = "" if include_empty else " and coalesce(n_turns, 0) > 0"
        return db.execute(
            "select id, agent, cwd, started, ended, coalesce(n_turns, 0), "
            "coalesce(nullif(name, ''), nullif(title, '')), outcome "
            f"from sessions where kind = 'main'{turns} "
            "order by coalesce(ended, started) desc, id"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        db.close()


def _prefixes(registry: Registry) -> list[tuple[str, str]]:
    """(unit name, cwd prefix) for every home present on this machine.

    Two prefixes per home: the resolved host path, and the container path
    scad mounts it at. A session that ran in a container records the latter.
    """
    out: list[tuple[str, str]] = []
    for unit in registry.units():
        for home in unit.homes:
            if home.path is None:
                continue
            out.append((unit.name, str(home.path.resolve())))
            out.append((unit.name, f"/workspace/{repo_of(home.name)}"))
    return out


def _under(cwd: str, prefix: str) -> bool:
    return cwd == prefix or cwd.startswith(prefix.rstrip("/") + "/")


def all_sessions(
    registry: Registry,
    index: Path,
    events_root: Path,
    include_empty: bool = False,
) -> list[Session]:
    """Every session scad knows about, with the units it belongs to."""
    attributed = attributions(root=events_root)
    prefixes = _prefixes(registry)
    out: list[Session] = []
    for sid, agent, cwd, started, ended, turns, label, outcome in _rows(index, include_empty):
        if sid in attributed:
            units, how = frozenset({attributed[sid]}), "attributed"
        else:
            units = frozenset(
                name for name, prefix in prefixes if cwd and _under(cwd, prefix)
            )
            how = "containment" if units else None
        out.append(Session(
            id=sid, agent=agent, cwd=cwd, started=started, ended=ended,
            turns=turns, label=label, outcome=outcome, units=units, how=how,
        ))
    return out


def for_unit(sessions: list[Session], name: str) -> list[Session]:
    return [s for s in sessions if name in s.units]


def unattributed(sessions: list[Session]) -> list[Session]:
    return [s for s in sessions if not s.units]
