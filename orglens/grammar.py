"""The one declaration of a tree's vocabulary.

Three blocks and nothing else: what exists, where documents live, what each
part is for. Every other module asks this one — none of them may know a noun
of their own, which `tests/test_vocabulary_face.py` enforces.

Nothing here filters. A directory matching an entity pattern is an entity; a
file matching an artifact glob is an artifact of that type. Completeness is
never a precondition for visibility: the previous grammar made it one, and it
cost four real entities and 88 documents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class EntityType:
    """A kind of thing, and the relative glob that finds one."""

    name: str
    pattern: str
    #: path within the entity -> what it is for. Authoring, never discovery.
    structure: dict[str, str] = field(default_factory=dict)

    @property
    def container(self) -> str:
        """The directory part of the pattern — where a new one is placed.

        Empty when the pattern names the directory itself, which is how a type
        comes to live directly inside its parent rather than under a bucket.
        """
        head, _, _ = self.pattern.rpartition("/")
        return head

    @property
    def files(self) -> dict[str, str]:
        return {k: v for k, v in self.structure.items() if not k.endswith("/")}

    @property
    def directories(self) -> dict[str, str]:
        return {k: v for k, v in self.structure.items() if k.endswith("/")}


@dataclass(frozen=True)
class ArtifactType:
    """A kind of document: where to look, and prose about what to call one."""

    name: str
    find: str
    means: str = ""

    @property
    def directory(self) -> str:
        head, _, _ = self.find.rpartition("/")
        return head


@dataclass(frozen=True)
class Grammar:
    version: int
    entity_types: dict[str, EntityType]
    artifact_types: dict[str, ArtifactType]
    #: The one document that says where an entity stands. Required: every
    #: entity has one, so an optional field would be a None branch in every
    #: consumer that is never taken. Declared rather than hardcoded — the
    #: engine may not know a noun — and one name per tree rather than per kind,
    #: which buys nothing technically and everything for a human browsing.
    driver: str

    def documents_for(self, entity_type: str) -> list[str]:
        """Where to look for an entity's status line, driver first.

        Precedence, not location: the line is found wherever it lives. This
        only decides which document is consulted first, which is why the
        driver is declared rather than inferred from list order — a reordering
        should not silently change what `status` reports.
        """
        structure = self.entity_types[entity_type].structure
        return [self.driver] + [
            k for k in structure if not k.endswith("/") and k != self.driver
        ]

    @classmethod
    def from_yaml(cls, path: Path) -> Grammar:
        data = yaml.safe_load(Path(path).read_text()) or {}
        if not data.get("driver"):
            raise ValueError(
                f"{path}: a grammar must declare `driver` — the document that "
                f"says where an entity stands"
            )
        declared = data.get("structure") or {}

        entity_types = {
            name: EntityType(
                name=name,
                pattern=pattern,
                structure=dict(declared.get(name) or {}),
            )
            for name, pattern in (data.get("entities") or {}).items()
        }

        artifact_types = {
            name: ArtifactType(
                name=name,
                find=body["find"],
                means=" ".join((body.get("means") or "").split()),
            )
            for name, body in (data.get("artifacts") or {}).items()
        }

        return cls(
            version=data.get("version", 2),
            driver=data.get("driver"),
            entity_types=entity_types,
            artifact_types=artifact_types,
        )
