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

The sessions come from scad's export, `scad session ls --json`, never from
its index file: the schema is scad's, and reading the file made it a contract
nobody had written down. scad does not know orglens exists; orglens asks scad
and joins the answer to units itself. The two file sessions under different
keys — scad by the directory a marker sits in, orglens by a declared unit
spanning several directories — and those keys are not made to match.
Directory names are the input; the unit is the output.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from orglens.events import attributions, dismissed
from orglens.homes import repo_of
from orglens.units import Registry

#: scad's own words for a session that can be picked back up.
OPEN = frozenset({"awaiting-user", "awaiting-question", "in-flight"})


def run_scad(argv: list[str]) -> list[dict]:
    """`scad <argv> --json`, parsed. No scad, an old scad, or a failure is an
    empty answer, not an error: a machine without scad has no sessions to
    show, which is ordinary. Tests replace this with a list."""
    try:
        done = subprocess.run(
            ["scad", *argv, "--json"], capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if done.returncode != 0:
        return []
    try:
        rows = json.loads(done.stdout)
    except ValueError:
        return []
    return rows if isinstance(rows, list) else []


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
    #: The newest turn with text: {ts, role, text}, text clipped by scad.
    last_turn: dict | None = None
    #: An open question the session left, if any.
    needs: str | None = None
    #: Why this session is nobody's, when someone has said so.
    dismissed: str | None = None
    #: The other live processes on this same session id, when scad reports
    #: any: [{pid, name, pane}]. Two writers on one transcript is how a
    #: session forks, so anything that opens one has to know.
    also_held_by: tuple = ()

    @property
    def open(self) -> bool:
        return self.outcome in OPEN

    @property
    def when(self) -> int | None:
        """The clock a listing sorts by: when it ended, else when it began."""
        return self.ended or self.started


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


def all_sessions(registry: Registry, events_root: Path) -> list[Session]:
    """Every main session scad knows about, each with the units it belongs to.

    Zero-turn rows are included: a session scad indexed at launch has none
    until its first turn lands, and it is exactly the one that is live. A
    listing hides them; a count and a live check must not. A session started
    by hand in a terminal is not a row until scad's next reindex.
    """
    attributed = attributions(root=events_root)
    gone = dismissed(root=events_root)
    prefixes = _prefixes(registry)

    def belongs(sid: str, cwd: str | None) -> tuple[frozenset[str], str | None]:
        if sid in attributed:
            return frozenset({attributed[sid]}), "attributed"
        # A dismissal is an answer, so containment does not get to overrule
        # it: a scratch session that happens to sit inside a home was still
        # never that unit's work.
        if sid in gone:
            return frozenset(), "dismissed"
        units = frozenset(name for name, prefix in prefixes if cwd and _under(cwd, prefix))
        return units, ("containment" if units else None)

    out: list[Session] = []
    for row in run_scad(["session", "ls", "--kind", "main", "--limit", "100000"]):
        sid = str(row.get("id") or "")
        if not sid:
            continue
        cwd = row.get("cwd")
        live = row.get("live") or None
        units, how = belongs(sid, cwd)
        # The name the person set reaches the registry at once and the index
        # only on reindex, so a live session's name comes from `live`.
        label = (live or {}).get("name") or row.get("name") or row.get("title") or None
        out.append(Session(
            id=sid, agent=str(row.get("agent") or ""), cwd=cwd,
            started=row.get("started"), ended=row.get("ended"),
            turns=int(row.get("n_turns") or 0), label=label,
            outcome=row.get("outcome"), live=live is not None,
            units=units, how=how,
            last_turn=row.get("last_turn") or None, needs=row.get("needs") or None,
            dismissed=gone.get(sid),
            also_held_by=tuple((live or {}).get("also_held_by") or ()),
        ))
    out.sort(key=lambda s: (s.when or 0, s.id), reverse=True)
    return out


def for_unit(sessions: list[Session], name: str) -> list[Session]:
    return [s for s in sessions if name in s.units]


def unattributed(sessions: list[Session], everything: bool = False) -> list[Session]:
    """The sessions nobody has claimed. Dismissed ones are decided, not
    undecided, so they leave the pile unless asked for."""
    return [s for s in sessions
            if not s.units and (everything or s.dismissed is None)]


def listed(sessions: list[Session], everything: bool = False) -> list[Session]:
    """What a listing shows, in the order it shows it.

    Running first: a just-launched session has no clock yet, and it is the
    one you most want to see. Without `everything`, the rows scad indexed
    at launch that have no turn yet are left out, unless they are running.
    """
    shown = [s for s in sessions if everything or s.turns or s.live]
    return sorted(shown, key=lambda s: (s.live, s.when or 0, s.id), reverse=True)


def short_ids(ids: list[str], floor: int = 8) -> dict[str, str]:
    """The shortest prefix of each id that no other id shares, at least
    `floor` characters. Eight is enough for a random UUID; codex threads are
    UUIDv7, whose first eight hex characters are a timestamp, so two threads
    started in one minute need a ninth or tenth to tell apart."""
    out: dict[str, str] = {}
    for sid in ids:
        n = floor
        while n < len(sid) and any(o != sid and o.startswith(sid[:n]) for o in ids):
            n += 1
        out[sid] = sid[:n]
    return out


def where(cwd: str | None) -> str:
    """A cwd short enough to read in a row: home-relative, tail-clipped."""
    if not cwd:
        return "—"
    home = str(Path.home())
    shown = "~" + cwd[len(home):] if cwd.startswith(home) else cwd
    return shown if len(shown) <= 64 else "…" + shown[-63:]
