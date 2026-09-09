"""What a directory looks like it is, so declaring it is one confirmation.

Every guess here comes from position — which is exactly the signal the units
model stopped treating as truth. That is not a contradiction: position is a
fine *suggestion* and a bad *fact*. The difference is whether a person says
yes, so nothing here writes anything, and every guess carries the reason it
was made.

Tested against the nine undeclared candidates in the real tree on 2026-09-09:
correct kind, parent and code home for all nine. It would still have proposed
the wrong homes for a client whose repositories are named after neither the
client nor the folder, which is why the proposal is editable and `check`'s
collision report stays the backstop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from orglens.grammar import Grammar
from orglens.units import Registry


@dataclass(frozen=True)
class Proposal:
    unit: str
    kind: str
    part_of: str | None
    homes: tuple[str, ...]
    why: dict[str, str] = field(default_factory=dict)


def _kind_for(path: Path, grammar: Grammar) -> tuple[str, str]:
    """The kind whose pattern this path matches, and why we think so."""
    for name, entity_type in grammar.entity_types.items():
        if path.match(entity_type.pattern):
            return name, f"it matches `{entity_type.pattern}`"
    return "", "nothing in the grammar matches this position — say which kind"


def home_name(path: Path, registry: Registry) -> str:
    """This directory as a home name: the repository it is in, plus the rest.

    An already-declared home name for this exact directory wins — that is a
    fact read off a marker, not a guess. Otherwise a repository root is named
    by itself, and a folder inside a repository is named `<repo>/<rest>`, the
    same shape `check`'s ladder would resolve later. The bare basename is the
    last resort, used only when nothing above the path is a repository at
    all — never returned for a directory that a repository already contains,
    which is what kept this from colliding with the code home found below.
    """
    for candidate in registry.scan():
        if candidate.path == path and candidate.marker_home:
            return candidate.marker_home
    for parent in [path, *path.parents]:
        if (parent / ".git").exists():
            if parent == path:
                return path.name
            return f"{parent.name}/{path.relative_to(parent)}"
    return path.name


def propose(path: Path, registry: Registry) -> Proposal:
    """What this directory looks like. Suggests; never writes."""
    path = Path(path).expanduser().resolve()
    why: dict[str, str] = {}

    kind, why["kind"] = _kind_for(path, registry.grammar)

    containing = registry.at(path.parent) if path.parent != path else None
    part_of = containing.name if containing else None
    if part_of:
        why["part_of"] = f"it sits inside {part_of}'s home"

    homes = [home_name(path, registry)]
    why["homes"] = "the folder itself"

    # A repository named after this folder is almost always its code home.
    for candidate in registry.scan():
        if candidate.name == path.name and candidate.path != path:
            homes.append(candidate.name)
            why["homes"] += f", and `{candidate.name}` shares its name"
            break

    return Proposal(unit=path.name, kind=kind, part_of=part_of,
                    homes=tuple(homes), why=why)
