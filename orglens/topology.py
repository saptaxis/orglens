"""Discovery — what is in the tree, found by pattern rather than declared.

Entities are found by matching each grammar pattern at the docs root, then
inside every entity found, until nothing new turns up. That loop is the whole
hierarchy: containment *is* the parent relationship, so no key names a depth
and nothing has to be told that one kind of thing lives inside another.

Nothing is filtered on completeness. A directory that matches is an entity
whether or not it holds the files the grammar suggests; `check` reports the
gap, and reporting is all it does.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from orglens.grammar import Grammar


@dataclass(frozen=True)
class Entity:
    name: str
    entity_type: str
    path: Path
    parent_name: str | None = None


@dataclass(frozen=True)
class Artifact:
    name: str
    artifact_type: str
    path: Path
    entity_name: str


class Topology:
    def __init__(self, docs_root: Path, grammar: Grammar):
        self.docs_root = Path(docs_root)
        self.grammar = grammar
        self._found: list[Entity] | None = None

    # ── discovery ────────────────────────────────────────────────────────

    def list_entities(self, entity_type: str | None = None) -> list[Entity]:
        """Every entity in the tree, at any depth.

        Terminates because each round descends at least one directory level.
        Held after the first walk: callers ask per entity per document kind, and
        re-walking the tree for each of those turns one scan into dozens.
        """
        if self._found is None:
            self._found = self._walk()
        if entity_type is not None:
            return [e for e in self._found if e.entity_type == entity_type]
        return self._found

    def _walk(self) -> list[Entity]:
        found: list[Entity] = []
        seen: set[Path] = set()
        frontier: list[tuple[Path, str | None]] = [(self.docs_root, None)]

        while frontier:
            deeper: list[tuple[Path, str | None]] = []
            for base, parent_name in frontier:
                for name, entity_type_ in self.grammar.entity_types.items():
                    for match in sorted(base.glob(entity_type_.pattern)):
                        if not match.is_dir() or match in seen:
                            continue
                        seen.add(match)
                        found.append(Entity(match.name, name, match, parent_name))
                        deeper.append((match, match.name))
            frontier = deeper

        return sorted(found, key=lambda e: e.path)

    def resolve(self, name: str) -> Entity:
        """Resolve a partial name to a single entity."""
        entities = self.list_entities()
        for candidates in (
            [e for e in entities if e.name == name],
            [e for e in entities if e.name.startswith(name)],
            [e for e in entities if name in e.name],
        ):
            if len(candidates) == 1:
                return candidates[0]
            if len(candidates) > 1:
                raise ValueError(
                    f"'{name}' matches multiple entities: "
                    + ", ".join(e.name for e in candidates)
                )
        raise ValueError(
            f"No entity '{name}' found. "
            f"Available: {', '.join(e.name for e in entities)}"
        )

    def children_of(self, entity: Entity) -> list[Entity]:
        """Entities nested anywhere beneath this one."""
        return [
            e for e in self.list_entities()
            if e.path != entity.path and entity.path in e.path.parents
        ]

    # ── documents ────────────────────────────────────────────────────────

    def find_artifacts(
        self, artifact_type: str, entity_name: str | None = None
    ) -> list[Artifact]:
        """Documents of a type, optionally scoped to an entity and its children.

        Every file the glob matches counts. The previous engine required the
        filename to parse against a template and silently dropped the rest,
        which hid 88 documents written under two other conventions.
        """
        found = self.grammar.artifact_types[artifact_type]
        entities = self.list_entities()
        if entity_name is not None:
            root = self.resolve(entity_name)
            entities = [root] + self.children_of(root)

        artifacts = []
        for entity in entities:
            for path in sorted(entity.path.glob(found.find)):
                if path.is_file():
                    artifacts.append(
                        Artifact(path.name, artifact_type, path, entity.name)
                    )
        return artifacts

    def documents(self, entity: Entity) -> list[Path]:
        """Top-level documents — the ones no artifact type claims."""
        return sorted(
            p for p in entity.path.glob("*.md")
            if p.is_file() and not p.name.startswith(".")
        )

    def subdirectories(self, entity: Entity) -> list[Path]:
        """What the entity actually holds, declared or not.

        This is the navigation surface. The grammar says what a part is *for*;
        only the tree knows what is there — `archive/`, `presentation/` and
        `infrastructure/` are real and were never declared anywhere.
        """
        return sorted(
            d for d in entity.path.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

    # ── creation ─────────────────────────────────────────────────────────

    def scaffold_entity(
        self, entity_type: str, name: str, parent: str | None = None
    ) -> Path:
        """Create an entity: a directory, plus whatever `structure` names.

        Placement comes from the pattern, so this cannot create something the
        discovery loop would not then find — the check below is that promise.
        """
        declared = self.grammar.entity_types[entity_type]
        base = self.resolve(parent).path if parent else self.docs_root

        relative = f"{declared.container}/{name}" if declared.container else name
        if not fnmatch(relative, declared.pattern):
            raise ValueError(
                f"'{name}' would not be found as a {entity_type}: "
                f"{relative!r} does not match {declared.pattern!r}"
            )

        target = base / relative
        if target.exists():
            raise ValueError(f"{target} already exists")
        target.mkdir(parents=True)

        for directory in declared.directories:
            (target / directory).mkdir(parents=True, exist_ok=True)
        for filename, means in declared.files.items():
            (target / filename).write_text(_stub(filename, means))

        self._found = None  # what was just created has to be discoverable now
        return target


def _stub(filename: str, means: str) -> str:
    """A new file says what it is for, in the grammar's own words."""
    title = Path(filename).stem.replace("-", " ").replace("_", " ").title()
    body = f"\n{means}\n" if means else ""
    return f"# {title}\n\n> **Status:** Pending\n{body}"
