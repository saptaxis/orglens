"""Topology operations — discover, scaffold, find entities and artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from orglens.grammar import Grammar


@dataclass
class Entity:
    name: str
    entity_type: str
    path: Path
    parent_name: str | None = None


@dataclass
class Artifact:
    name: str
    artifact_type: str
    path: Path
    entity_name: str


class Topology:
    def __init__(self, docs_root: Path, grammar: Grammar):
        self.docs_root = docs_root
        self.grammar = grammar

    def list_entities(self, entity_type: str | None = None) -> list[Entity]:
        """Discover all entities, optionally filtered by type."""
        entities = []
        types_to_scan = (
            [entity_type] if entity_type
            else [k for k in self.grammar.entity_types if k != "experiment"]
        )

        for type_name in types_to_scan:
            et = self.grammar.entity_types[type_name]
            if et.parent_dir:
                parent = self.docs_root / et.parent_dir
                if parent.exists():
                    for d in sorted(parent.iterdir()):
                        if d.is_dir() and self._looks_like_entity(d, et):
                            entities.append(Entity(
                                name=d.name,
                                entity_type=type_name,
                                path=d,
                            ))
                            # Discover children
                            for child_type in et.children:
                                child_et = self.grammar.entity_types[child_type]
                                entities.extend(
                                    self._discover_children(d, child_type, child_et, d.name)
                                )

        if entity_type == "experiment":
            # Scan inside all research programs
            rp_et = self.grammar.entity_types["research-program"]
            parent = self.docs_root / rp_et.parent_dir
            if parent.exists():
                for rp_dir in sorted(parent.iterdir()):
                    if rp_dir.is_dir():
                        expt_et = self.grammar.entity_types["experiment"]
                        entities.extend(
                            self._discover_children(rp_dir, "experiment", expt_et, rp_dir.name)
                        )

        return entities

    def _discover_children(self, parent_dir: Path, child_type: str, child_et, parent_name: str) -> list[Entity]:
        """Discover child entities within a parent directory."""
        children = []
        if child_et.dir_pattern:
            prefix = child_et.dir_pattern.split("{")[0]  # e.g. "expt-"
            for d in sorted(parent_dir.iterdir()):
                if d.is_dir() and d.name.startswith(prefix):
                    if self._looks_like_entity(d, child_et):
                        children.append(Entity(
                            name=d.name,
                            entity_type=child_type,
                            path=d,
                            parent_name=parent_name,
                        ))
        return children

    def _looks_like_entity(self, path: Path, et) -> bool:
        """Check if a directory looks like a valid entity of the given type."""
        for req in et.required_files:
            if not (path / req).exists():
                return False
        return True

    def resolve(self, name: str) -> Entity:
        """Resolve a partial name to a single entity."""
        all_entities = self.list_entities()
        # Exact match first
        exact = [e for e in all_entities if e.name == name]
        if len(exact) == 1:
            return exact[0]
        # Prefix match
        prefix = [e for e in all_entities if e.name.startswith(name)]
        if len(prefix) == 1:
            return prefix[0]
        # Substring match
        substr = [e for e in all_entities if name in e.name]
        if len(substr) == 1:
            return substr[0]
        if len(substr) == 0 and len(prefix) == 0:
            raise ValueError(
                f"No entity '{name}' found. "
                f"Available: {', '.join(e.name for e in all_entities)}"
            )
        matches = prefix if prefix else substr
        raise ValueError(
            f"'{name}' matches multiple entities: "
            f"{', '.join(e.name for e in matches)}. Be more specific."
        )

    def scaffold_entity(self, entity_type: str, name: str, parent: str | None = None) -> Path:
        """Create a new entity with the correct directory structure."""
        et = self.grammar.entity_types[entity_type]

        if et.parent_of:
            # Child entity (e.g. experiment) — needs parent resolution
            if not parent:
                raise ValueError(f"{entity_type} requires a parent (e.g. --parent <research-program>)")
            parent_entity = self.resolve(parent)
            # Auto-number using dir_pattern
            n = self._next_child_number(parent_entity.path, et)
            dir_name = et.dir_pattern.replace("{n}", str(n)).replace("{name}", name)
            entity_dir = parent_entity.path / dir_name
        elif et.parent_dir:
            entity_dir = self.docs_root / et.parent_dir / name
        else:
            raise ValueError(f"Cannot scaffold entity type '{entity_type}': no parent_dir or parent_of")

        if entity_dir.exists():
            raise FileExistsError(f"{entity_dir} already exists")

        entity_dir.mkdir(parents=True)

        for subdir in et.directories:
            (entity_dir / subdir).mkdir()

        for req_file in et.required_files:
            filepath = entity_dir / req_file
            filepath.write_text(self._template_for_file(req_file, name))

        return entity_dir

    def _next_child_number(self, parent_dir: Path, child_et) -> int:
        """Find the next sequential number for a child entity."""
        prefix = child_et.dir_pattern.split("{")[0]
        existing = [
            d.name for d in parent_dir.iterdir()
            if d.is_dir() and d.name.startswith(prefix)
        ]
        if not existing:
            return 1
        numbers = []
        for name in existing:
            match = re.match(rf"{re.escape(prefix)}(\d+)", name)
            if match:
                numbers.append(int(match.group(1)))
        return max(numbers) + 1 if numbers else 1

    def _template_for_file(self, filename: str, entity_name: str) -> str:
        """Generate initial content for a required file."""
        title = entity_name.replace("-", " ").title()
        templates = {
            "overview.md": f"# Overview\n\n> **Status:** Pending\n",
            "design.md": f"# Design\n\n> **Status:** Pending\n",
            "research-question.md": f"# Research Question\n\n> **Status:** Pending\n",
            "research-program-state.md": (
                f"# Research Program State\n\n"
                f"> **Last updated:** {date.today().strftime('%Y-%m-%d')}\n"
            ),
        }
        return templates.get(filename, f"# {title}\n")

    def find_artifacts(self, artifact_type: str, entity_name: str | None = None) -> list[Artifact]:
        """Find artifacts, optionally scoped to an entity (recursive for programs)."""
        at = self.grammar.artifact_types[artifact_type]

        if entity_name:
            entity = self.resolve(entity_name)
            return self._find_artifacts_in(at, entity.path, entity.name)
        else:
            # Search everywhere, but skip child entity types —
            # parent's recursive search already covers them
            artifacts = []
            for entity in self.list_entities():
                et = self.grammar.entity_types[entity.entity_type]
                if et.parent_of:
                    continue
                artifacts.extend(self._find_artifacts_in(at, entity.path, entity.name))
            return artifacts

    def _find_artifacts_in(self, at, entity_path: Path, entity_name: str) -> list[Artifact]:
        """Find artifacts of a given type within an entity directory (recursive)."""
        artifacts = []
        target_dir = entity_path / at.directory
        if target_dir.exists():
            for f in sorted(target_dir.iterdir()):
                if f.is_file() and f.suffix == ".md":
                    parsed = at.parse_name(f.name)
                    if parsed is not None:
                        artifacts.append(Artifact(
                            name=f.name,
                            artifact_type=at.name,
                            path=f,
                            entity_name=entity_name,
                        ))
        # Also search child entity directories
        et = None
        for etype in self.grammar.entity_types.values():
            if etype.parent_dir and entity_path.parent.name == etype.parent_dir:
                et = etype
                break
            if etype.parent_of and entity_path.name.startswith("expt-"):
                return artifacts  # Don't recurse further from experiments

        if et and et.children:
            for child_type in et.children:
                child_et = self.grammar.entity_types[child_type]
                if child_et.dir_pattern:
                    prefix = child_et.dir_pattern.split("{")[0]
                    for d in sorted(entity_path.iterdir()):
                        if d.is_dir() and d.name.startswith(prefix):
                            artifacts.extend(self._find_artifacts_in(at, d, d.name))

        return artifacts

    def next_artifact_number(self, artifact_type: str, entity_name: str) -> int:
        """Get the next sequential number for an artifact type in an entity."""
        at = self.grammar.artifact_types[artifact_type]
        entity = self.resolve(entity_name)
        target_dir = entity.path / at.directory
        if not target_dir.exists():
            return 1
        numbers = []
        for f in target_dir.iterdir():
            if f.is_file():
                parsed = at.parse_name(f.name)
                if parsed and "nn" in parsed:
                    numbers.append(parsed["nn"])
        return max(numbers) + 1 if numbers else 1

    def scaffold_artifact(self, artifact_type: str, entity_name: str, topic: str) -> Path:
        """Create a new artifact with correct numbering and dating."""
        at = self.grammar.artifact_types[artifact_type]
        entity = self.resolve(entity_name)
        target_dir = entity.path / at.directory

        if not target_dir.exists():
            target_dir.mkdir(parents=True)

        today = date.today()
        date_str = today.strftime("%b%d%Y")  # e.g. "Feb272026"

        if "{NN}" in at.pattern:
            nn = self.next_artifact_number(artifact_type, entity_name)
        else:
            nn = None

        filename = at.generate_name(nn=nn, topic=topic, date_str=date_str)
        filepath = target_dir / filename

        # Generate initial content
        if nn:
            title = f"# {nn:02d} — {topic.replace('-', ' ').title()}"
        else:
            title = f"# {topic.replace('-', ' ').title()}"

        filepath.write_text(f"{title}\n\n> **Status:** Pending\n")
        return filepath
