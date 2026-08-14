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
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches
from pathlib import Path

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
class Report:
    drifted: list[Drift] = field(default_factory=list)
    #: Directories that look like work and have not declared themselves. The
    #: migration worklist, and the reason nothing goes dark while the tree is
    #: half declared.
    undeclared: list[Path] = field(default_factory=list)
    #: (unit, home) pairs where identity came only from the directory name.
    #: Renaming such a directory detaches the home silently, which is the one
    #: failure the ladder cannot prevent — only announce.
    weak: list[tuple[str, str]] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.drifted or self.undeclared or self.weak)


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

    weak = [
        (unit.name, home.name)
        for unit in units
        for home in unit.homes
        if home.how == "name"
    ]

    return Report(
        drifted=drifted,
        undeclared=registry.candidates(),
        weak=weak,
    )
