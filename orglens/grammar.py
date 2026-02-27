"""Grammar loading and resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class EntityType:
    name: str
    parent_dir: str | None = None
    parent_of: str | None = None
    dir_pattern: str | None = None
    required_files: list[str] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    state_file: str | None = None


@dataclass
class ArtifactType:
    name: str
    directory: str
    pattern: str

    def generate_name(self, nn: int | None, topic: str, date_str: str | None) -> str:
        """Generate a filename from the pattern."""
        result = self.pattern
        if nn is not None:
            result = result.replace("{NN}", f"{nn:02d}")
        if topic:
            result = result.replace("{topic}", topic)
        if date_str:
            result = result.replace("{MonDDYYYY}", date_str)
        return result

    def parse_name(self, filename: str) -> dict | None:
        """Parse a filename back into components. Returns None if no match."""
        # Build regex from pattern
        regex = self.pattern
        regex = regex.replace("{NN}", r"(?P<nn>\d+)")
        regex = regex.replace("{topic}", r"(?P<topic>[a-z0-9-]+)")
        regex = regex.replace("{MonDDYYYY}", r"(?P<date>[A-Z][a-z]{2}\d{6,8})")
        regex = "^" + regex + "$"
        match = re.match(regex, filename)
        if not match:
            return None
        result = match.groupdict()
        if "nn" in result:
            result["nn"] = int(result["nn"])
        return result


@dataclass
class Grammar:
    version: int
    entity_types: dict[str, EntityType]
    artifact_types: dict[str, ArtifactType]

    @classmethod
    def from_yaml(cls, path: Path) -> Grammar:
        """Load grammar from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        entity_types = {}
        for name, spec in data.get("entity_types", {}).items():
            entity_types[name] = EntityType(
                name=name,
                parent_dir=spec.get("parent_dir"),
                parent_of=spec.get("parent_of"),
                dir_pattern=spec.get("dir_pattern"),
                required_files=spec.get("required_files", []),
                directories=spec.get("directories", []),
                children=spec.get("children", []),
                state_file=spec.get("state_file"),
            )

        artifact_types = {}
        for name, spec in data.get("artifacts", {}).items():
            artifact_types[name] = ArtifactType(
                name=name,
                directory=spec["directory"],
                pattern=spec["pattern"],
            )

        return cls(
            version=data.get("version", 1),
            entity_types=entity_types,
            artifact_types=artifact_types,
        )
