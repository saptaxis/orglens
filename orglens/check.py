"""Where the tree has drifted from what the grammar describes.

An audit, never a gate. Nothing calls it, nothing is hidden or blocked by what
it finds, and it always exits 0. It exists so drift can be cleaned up when you
feel like tidying — which is the opposite of the previous design, where the
same information was expressed by making four real entities invisible.

It reports entities only. Once filenames stopped being parsed, the 88 documents
that do not match a template stopped being defects: they are the other two
naming conventions actually in use, and listing them would be noise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches
from pathlib import Path

from orglens.topology import Topology


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
    #: Patterns that match nothing anywhere. A mistyped glob finds no entities
    #: and raises nothing, so without this it fails silently — the one new way
    #: this design can go wrong.
    barren: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.drifted or self.barren)


def run(topo: Topology) -> Report:
    entities = topo.list_entities()
    drifted = []

    for entity in entities:
        # Files only. An absent directory is not drift — it means nothing has
        # been written there yet, and reporting it turned four honest lines
        # into fourteen, most of them "missing specs/" on projects that simply
        # have no design documents. Scaffolding empty directories to silence a
        # report would be worse than the report.
        declared = topo.grammar.entity_types[entity.entity_type].files
        present = [p.name for p in entity.path.iterdir()]
        missing = []
        for name in declared:
            if (entity.path / name).exists():
                continue
            close = get_close_matches(name, present, n=1, cutoff=0.55)
            missing.append(Missing(name=name, resembles=close[0] if close else None))
        if missing:
            drifted.append(Drift(entity=entity.name, path=entity.path, missing=missing))

    seen = {e.entity_type for e in entities}
    barren = [
        f"{name}: {entity_type.pattern}"
        for name, entity_type in topo.grammar.entity_types.items()
        if name not in seen
    ]
    barren += [
        f"{name}: {artifact_type.find}"
        for name, artifact_type in topo.grammar.artifact_types.items()
        if not topo.find_artifacts(name)
    ]

    return Report(drifted=drifted, barren=barren)
