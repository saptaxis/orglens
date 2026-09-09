"""Where the tree has drifted from what the grammar describes, and what has
not declared itself at all.

An audit, never a gate. Nothing calls it, nothing is hidden or blocked by what
it finds, and it always exits 0. It exists so drift can be cleaned up when you
feel like tidying — which is the opposite of the previous design, where the
same information was expressed by making four real entities invisible.

It reports declared units only for drift. Once filenames stopped being
parsed, the 88 documents that do not match a template stopped being defects:
they are the other two naming conventions actually in use, and listing them
would be noise. What has not declared itself at all is a different question,
answered by `undeclared` — the migration worklist, and the reason nothing
goes dark while the tree is half declared.

A glob that matches nothing anywhere is a different silent failure again —
not an undeclared directory, but a mistyped or misplaced pattern that quietly
stops finding documents it should. `operators/*.md` once pointed one
directory too high and found nothing, and nothing said so. `unmatched` is
what says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches
from pathlib import Path

from orglens import documents
from orglens.homes import Candidate, candidates_for
from orglens.units import Registry


@dataclass(frozen=True)
class Missing:
    name: str
    #: A file already present whose name is close. Two of four real cases are
    #: a near-miss rather than an absence, and saying so is what makes this
    #: worth running instead of a scold.
    resembles: str | None = None


@dataclass(frozen=True)
class Drift:
    #: The unit, not one of its homes. A declared file belongs to whichever
    #: home the grammar's structure actually implies — a code repository
    #: should never carry `overview.md` — so naming a home here would point
    #: the fix at the wrong place as often as the right one.
    entity: str
    missing: list[Missing] = field(default_factory=list)


@dataclass(frozen=True)
class Duplicate:
    """A unit name declared by more than one marker — a `cp -R`, a git
    worktree, a Dropbox conflicted copy, a template folder. Left unreported,
    every consumer that resolves this name by exact match raises, which used
    to take `status`, `view`, `snapshot` and `find` down for every unit, not
    only this one.
    """
    name: str
    paths: list[Path] = field(default_factory=list)


@dataclass(frozen=True)
class Collision:
    """A home name that more than one candidate directory could have
    answered for — the ladder still picks one, by scan order, but the tie
    is real. `weak` says a resolution is fragile; this says it was actually
    contested.
    """
    unit: str
    home: str
    paths: list[Path] = field(default_factory=list)


@dataclass(frozen=True)
class Report:
    drifted: list[Drift] = field(default_factory=list)
    #: Directories that look like work and have not declared themselves. The
    #: migration worklist, and the reason nothing goes dark while the tree is
    #: half declared.
    undeclared: list[Path] = field(default_factory=list)
    #: (unit, home, how) rows where identity came only from the directory
    #: name, or from a git remote's repository-name tail while some other
    #: scanned candidate shares that same tail. Both discard information a
    #: marker would have kept, but they are not equally dangerous: a bare
    #: name is fragile the moment that one directory is renamed, whether or
    #: not anything collides today, so it is always reported. A remote tail
    #: is only a hazard when an owner collision is actually live among the
    #: candidates on disk — on a real tree every home resolves through the
    #: remote rung, so reporting it unconditionally drowned the rows that
    #: are an actual worklist in noise that fires whether or not the risk is
    #: real. `how` is carried so the printer can say which of the two
    #: actually happened, rather than always naming the first.
    weak: list[tuple[str, str, str]] = field(default_factory=list)
    #: Document kinds whose glob matches nothing anywhere. A mistyped glob
    #: finds no documents and raises nothing, so without this it fails
    #: silently — the one way this design can still go wrong quietly.
    unmatched: list[str] = field(default_factory=list)
    #: Unit names declared by more than one marker.
    duplicates: list[Duplicate] = field(default_factory=list)
    #: Home names more than one candidate directory could have satisfied.
    collisions: list[Collision] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(
            self.drifted
            or self.undeclared
            or self.weak
            or self.unmatched
            or self.duplicates
            or self.collisions
        )


def run(registry: Registry) -> Report:
    units = registry.units()
    drifted = []

    for unit in units:
        # `kind` is a free-ish label and need not be a key in the grammar's
        # entity types — an unknown kind means no declared files to check,
        # not a crash.
        declared = (
            registry.grammar.entity_types[unit.kind].files
            if unit.kind in registry.grammar.entity_types
            else {}
        )
        if not declared:
            continue

        # What each home actually holds, gathered once so a declared file
        # can be checked against every home before it is called missing —
        # a documents home carrying `overview.md` clears the code homes
        # that a unit also lives in, which should never carry that file.
        present_by_home: list[list[str]] = []
        for home in unit.paths:
            try:
                present_by_home.append([p.name for p in home.iterdir()])
            except OSError:
                # A home can vanish between the sweep and the read. An audit
                # that raises on the thing it is auditing is worse than one
                # that reports nothing about it.
                continue

        missing = []
        for name in declared:
            if any(name in present for present in present_by_home):
                continue
            # The file that resembles this one may live in a home that was
            # not the first checked, so the hint has to search all of them.
            close = None
            for present in present_by_home:
                match = get_close_matches(name, present, n=1, cutoff=0.55)
                if match:
                    close = match[0]
                    break
            missing.append(Missing(name=name, resembles=close))
        if missing:
            drifted.append(Drift(entity=unit.name, missing=missing))

    # The same scan and the same `candidates_for` the collision report below
    # uses — reused, not re-run, and cached per home name since several units
    # can share one. A rung a home actually resolved through is guaranteed to
    # be the rung `candidates_for` reports rivals at, since both walk the same
    # `_rungs` over the same candidates.
    scan = registry.scan()
    rivals_by_home: dict[str, list[Candidate]] = {}

    def rivals_for(home_name: str) -> list[Candidate]:
        if home_name not in rivals_by_home:
            rivals_by_home[home_name] = candidates_for(home_name, scan)
        return rivals_by_home[home_name]

    # `name` discards everything but a directory's basename, and is fragile
    # regardless of what else is on disk today — renaming that one directory
    # detaches it whether or not anything currently collides, so it is always
    # weak. `remote` discards the host and owner, keeping only the
    # repository-name tail, but that looseness is only a live hazard when
    # some other scanned candidate actually shares the tail — on the real
    # tree every home resolves through this rung, so flagging it
    # unconditionally reported a risk that was present nowhere and drowned
    # the rows that matter.
    weak = [
        (unit.name, home.name, home.how)
        for unit in units
        for home in unit.homes
        if home.how == "name"
        or (home.how == "remote" and len(rivals_for(home.name)) > 1)
    ]

    # `documents.find` matches a kind's container by name at any depth
    # rather than taking the glob text literally, so a document one level
    # below where the pattern's text reaches — `plans/archive/x.md` for
    # `plans/*.md` — still counts as a match rather than a false unmatched.
    unmatched = [
        name
        for name in registry.grammar.artifact_types
        if not documents.find(registry, name)
    ]

    by_name: dict[str, list[Path]] = {}
    for unit in units:
        by_name.setdefault(unit.name, []).append(unit.declared_at)
    duplicates = [
        Duplicate(name=name, paths=sorted(paths))
        for name, paths in sorted(by_name.items())
        if len(paths) > 1
    ]

    seen: set[tuple[str, str]] = set()
    collisions = []
    for unit in units:
        for home in unit.homes:
            # `declaring` and `absent` never walked the ladder in the first
            # place — `declaring` is the directory a marker was read from,
            # pinned directly rather than resolved by name, and re-running
            # the ladder on its bare basename (the ordinary case for a
            # subfolder declaration with no `home:` key) would "find" every
            # unrelated directory sharing that name as a contest that never
            # happened. Only a name the ladder actually walked can have been
            # actually contested.
            if home.how not in ("marker", "remote", "name"):
                continue
            key = (unit.name, home.name)
            if key in seen:
                continue
            seen.add(key)
            rivals = rivals_for(home.name)
            if len(rivals) > 1:
                collisions.append(
                    Collision(
                        unit=unit.name,
                        home=home.name,
                        paths=sorted(c.path for c in rivals),
                    )
                )

    return Report(
        drifted=drifted,
        undeclared=registry.candidates(),
        weak=weak,
        unmatched=unmatched,
        duplicates=duplicates,
        collisions=collisions,
    )
