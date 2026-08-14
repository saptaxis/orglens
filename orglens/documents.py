"""A document belongs to a home by containment, not by glob depth.

The old globs reached exactly one level: `plans/*.md` relative to an entity.
That worked only because every folder holding plans happened to be an entity,
and it failed the moment one was not — measured on physics-priors-latent-space,
81 plans on disk and 75 visible: two in `infrastructure/plans/`, which matches
no pattern, and four in `plans/archive/`, one level too deep.

Containment is also what makes regrouping free. Leave a group of experiments
undeclared and the programme owns their documents; declare them later and the
documents follow, with nothing renamed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orglens.units import Registry, Unit


@dataclass(frozen=True)
class Document:
    name: str
    kind: str
    path: Path
    unit: str


def _claimed_by_parts(registry: Registry, unit: Unit) -> list[Path]:
    """Home paths belonging to units that declared themselves part of this one."""
    return [
        p.resolve()
        for part in registry.parts_of(unit)
        for p in part.paths
    ]


def _containers(home: Path, directory: str) -> list[Path]:
    """Every directory under `home` that could hold this kind's documents.

    A kind's `find` names a container (`plans`) and a file pattern (`*.md`).
    `Path.rglob("plans/*.md")` only reaches one level below a directory
    literally named `plans` — it does not see `plans/archive/*.md`. So the
    container is matched by name at any depth, and each match is then
    searched for the file pattern at any depth in turn, which is what lets
    an archived plan still be found. When a kind has no container of its
    own — `doc`, whose pattern is a bare `*.md` — the home itself is the
    only container, which is also what keeps `doc` a catch-all rather than
    one more directory-bound kind.
    """
    if not directory:
        return [home]
    return sorted(d for d in home.rglob(directory) if d.is_dir())


def find(
    registry: Registry, kind: str, unit_name: str | None = None
) -> list[Document]:
    """Documents of a kind, at any depth under a unit's homes.

    A container nested inside a same-named container — an archived
    experiment's own `plans/` preserved under the parent's `plans/archive/`
    — matches `_containers` twice, so the file under it would otherwise be
    yielded once per container that reaches it. Deduplicated on the
    resolved path rather than by excluding nested containers: a file is one
    document and belongs to a unit once, which covers every way containers
    can overlap rather than only the same-name nesting found so far. Order
    is the first occurrence, so it stays the stable, sorted order below.
    """
    artifact = registry.grammar.artifact_types[kind]
    file_pattern = Path(artifact.find).name
    units = (
        [registry.resolve(unit_name)] if unit_name is not None else registry.units()
    )

    found: list[Document] = []
    seen: set[Path] = set()
    for unit in units:
        excluded = _claimed_by_parts(registry, unit)
        for home in unit.paths:
            for container in _containers(home, artifact.directory):
                for path in sorted(container.rglob(file_pattern)):
                    if not path.is_file():
                        continue
                    resolved = path.resolve()
                    if resolved in seen:
                        continue
                    if any(
                        e == resolved or e in resolved.parents for e in excluded
                    ):
                        continue
                    seen.add(resolved)
                    found.append(Document(path.name, kind, path, unit.name))
    return found


def loose(unit: Unit) -> list[Path]:
    """Top-level documents in each home — backlogs, handoffs, dated notes."""
    return sorted(
        p
        for home in unit.paths
        for p in home.glob("*.md")
        if p.is_file() and not p.name.startswith(".")
    )


def subdirectories(unit: Unit) -> list[Path]:
    """What each home actually holds, declared or not.

    The grammar says what a part is *for*; only the tree knows what is there —
    `archive/`, `infrastructure/` and `presentation/` are real and were never
    declared anywhere.
    """
    return sorted(
        d
        for home in unit.paths
        for d in _entries(home)
        if d.is_dir() and not d.name.startswith(".")
    )


def _entries(home: Path) -> list[Path]:
    """What a home holds, or nothing if it has gone. Never raises.

    `glob` and `rglob` already return empty for a missing directory; only
    `iterdir` raises, and a listing that raises on the one home someone
    deleted would take the whole view down with it.
    """
    try:
        return list(home.iterdir())
    except OSError:
        return []
