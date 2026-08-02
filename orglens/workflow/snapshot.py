"""Packet snapshot — filenames, frontmatter, and recorded facts.

The engine does not open a file it did not write. What a document *says* is
data for the next node; the only things routing may see are which files exist,
what their frontmatter declares, and what run state records.

That line is why `SECTION_NAMES` and a `decisions-NN` regex used to live here
and no longer do: both made the deck-agnostic layer know what an essay is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from orglens.workflow.runstate import read_entries


@dataclass
class RoundInfo:
    number: int


@dataclass
class PacketSnapshot:
    root: Path
    files: list[str] = field(default_factory=list)
    brief: str | None = None
    brief_frontmatter: dict = field(default_factory=dict)
    artifact: str | None = None
    artifact_canonical: bool = True
    rounds: dict[int, RoundInfo] = field(default_factory=dict)
    runs: list[dict] = field(default_factory=list)


def _parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    return yaml.safe_load(text[3:end]) or {}


def _artifact_family_match(name: str, family: str) -> int | None:
    """Version number if `name` belongs to the artifact family.

    Permissive per I1a: draft.md, draft2.md, draft-v2.md all parse, and a bare
    name is version 1.
    """
    match = re.fullmatch(rf"{re.escape(family)}[-_]?v?(\d*)\.md", name)
    if not match:
        return None
    return int(match.group(1)) if match.group(1) else 1


def _round_pattern(workflow: dict) -> re.Pattern:
    """Compile the deck's declared round record pattern.

    `decisions-{NN}.md` -> decisions-(\\d+)\\.md. The engine has no default;
    a deck that records rounds must say how.
    """
    record = workflow.get("rounds", {}).get("record")
    if not record:
        return re.compile(r"(?!)")  # matches nothing
    escaped = re.escape(record).replace(re.escape("{NN}"), r"(\d+)")
    return re.compile(escaped)


def read_packet(root: Path, workflow: dict) -> PacketSnapshot:
    root = Path(root)
    snap = PacketSnapshot(root=root)
    if not root.is_dir():
        return snap

    snap.files = sorted(p.name for p in root.iterdir() if p.is_file())

    family = workflow.get("artifact", {}).get("family", "draft")
    canonical = workflow.get("artifact", {}).get("canonical")
    round_pattern = _round_pattern(workflow)
    best_version = -1

    for name in snap.files:
        if name.endswith("-brief.md") or name == "brief.md":
            snap.brief = name
            snap.brief_frontmatter = _parse_frontmatter((root / name).read_text())
            continue

        version = _artifact_family_match(name, family)
        if version is not None and version > best_version:
            best_version = version
            snap.artifact = name
            continue

        round_match = round_pattern.fullmatch(name)
        if round_match:
            number = int(round_match.group(1))
            snap.rounds[number] = RoundInfo(number=number)

    if snap.artifact is not None and canonical:
        snap.artifact_canonical = snap.artifact == canonical

    snap.runs = read_entries(root)
    return snap
