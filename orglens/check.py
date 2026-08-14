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
from orglens.homes import candidates_for
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
    entity: str
    path: Path
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
    #: (unit, home) pairs where identity came only from the directory name or
    #: a git remote's repository-name tail. Both discard information a marker
    #: would have kept — a rename detaches the first silently, an owner
    #: collision resolves the second silently and confidently — which is the
    #: one failure the ladder cannot prevent, only announce.
    weak: list[tuple[str, str]] = field(default_factory=list)
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
        for home in unit.paths:
            try:
                present = [p.name for p in home.iterdir()]
            except OSError:
                # A home can vanish between the sweep and the read. An audit
                # that raises on the thing it is auditing is worse than one
                # that reports nothing about it.
                continue
            missing = []
            for name in declared:
                if (home / name).exists():
                    continue
                close = get_close_matches(name, present, n=1, cutoff=0.55)
                missing.append(Missing(name=name, resembles=close[0] if close else None))
            if missing:
                drifted.append(Drift(entity=unit.name, path=home, missing=missing))

    # `name` discards everything but a directory's basename; `remote` discards
    # the host and owner, keeping only the repository-name tail. Both can
    # answer confidently for the wrong directory, which is exactly the
    # failure `weak` exists to surface — the old filter caught only the
    # first of the two.
    weak = [
        (unit.name, home.name)
        for unit in units
        for home in unit.homes
        if home.how in ("name", "remote")
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

    scan = registry.scan()
    seen: set[tuple[str, str]] = set()
    collisions = []
    for unit in units:
        for home in unit.homes:
            key = (unit.name, home.name)
            if key in seen:
                continue
            seen.add(key)
            rivals = candidates_for(home.name, scan)
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
