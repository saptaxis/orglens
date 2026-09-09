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


def _claimed_by(registry: Registry, unit: Unit) -> list[Path]:
    """Home paths this unit's documents must not claim.

    Two different reasons a directory is someone else's: it declared
    `part_of` this unit — the roll-up relationship, unaffected by where the
    directories actually sit — or its home simply lies inside this unit's
    own home, regardless of whether `part_of` was ever written. The spec
    says a unit's documents are "everything matching under its homes, minus
    whatever a nested unit's home claims" — containment, not only declared
    parentage, decides ownership. A unit declared nested in another's home
    without `part_of` used to have its documents counted by both; this is
    what stops that. A home identical to one of this unit's own (the
    ordinary shared-home case) is deliberately left unclaimed here — only a
    genuinely nested *other* home is excluded.
    """
    own = {p.resolve() for p in unit.paths}
    claimed = {p.resolve() for part in registry.parts_of(unit) for p in part.paths}
    for other in registry.units():
        if other.name == unit.name:
            continue
        for p in other.paths:
            resolved = p.resolve()
            if resolved not in own and any(resolved.is_relative_to(o) for o in own):
                claimed.add(resolved)
    return sorted(claimed)


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
    registry: Registry, kind: str, unit: Unit | str | None = None
) -> list[Document]:
    """Documents of a kind, at any depth under a unit's homes.

    `unit` takes a `Unit` the caller already resolved, a bare name for
    genuine user input (`orglens find plan <name>`), or nothing for every
    unit. A caller iterating `registry.units()` and calling back in with
    `unit.name` was re-resolving a name that was never ambiguous in the
    first place — and two markers declaring the same unit name (a `cp -R`,
    a worktree, a Dropbox conflicted copy) turned that into `Registry.resolve`
    raising out of the loop, taking every *other* unit's row down with it.
    Accepting the `Unit` itself skips resolution altogether; only a plain
    string still asks `resolve` to adjudicate, which is the right place for
    that question to be asked and answered.

    A container nested inside a same-named container — an archived
    experiment's own `plans/` preserved under the parent's `plans/archive/`
    — matches `_containers` twice, so the file under it would otherwise be
    yielded once per container that reaches it. Deduplicated on the
    resolved path, but *per unit*, not across the whole call: within one
    unit a file is counted once however many containers enclose it, while
    two units that share a home each see the file, because that is what a
    shared home is for — the spec is explicit that the same repository can
    be a home of two different units, and a shared library genuinely
    belongs to both. A global dedup would hand the file to whichever unit
    happened to sort first and silently drop it for the other, which is a
    unit losing its own documents, not a duplicate being removed. Order is
    the first occurrence within each unit, so it stays the stable, sorted
    order below.
    """
    artifact = registry.grammar.artifact_types[kind]
    file_pattern = Path(artifact.find).name
    if unit is None:
        units = registry.units()
    elif isinstance(unit, Unit):
        units = [unit]
    else:
        units = [registry.resolve(unit)]

    found: list[Document] = []
    for one in units:
        excluded = _claimed_by(registry, one)
        seen: set[Path] = set()
        for home in one.paths:
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
                    if any(part.startswith(".") for part in path.relative_to(home).parts):
                        continue
                    seen.add(resolved)
                    found.append(Document(path.name, kind, path, one.name))
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
