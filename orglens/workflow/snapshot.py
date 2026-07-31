"""Packet snapshot — pure filesystem facts for one unit of work."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SECTION_NAMES = ("Proposed", "Accept", "Modify", "Reject", "Auto-applied")


@dataclass
class RoundInfo:
    number: int
    sections: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class AdoptionInfo:
    sections: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class PacketSnapshot:
    root: Path
    files: list[str] = field(default_factory=list)
    brief: str | None = None
    brief_frontmatter: dict = field(default_factory=dict)
    artifact: str | None = None
    artifact_canonical: bool = True
    rounds: dict[int, RoundInfo] = field(default_factory=dict)
    adoption: AdoptionInfo | None = None
    runs: list[dict] = field(default_factory=list)


def _parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    return yaml.safe_load(text[3:end]) or {}


def _parse_sections(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    current = None
    for line in text.split("\n"):
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            name = heading.group(1)
            current = name if name in SECTION_NAMES else None
            if current:
                out[current] = []
            continue
        if current and line.startswith("- "):
            out[current].append(line[2:].strip())
    return out


def _artifact_family_match(name: str, family: str) -> int | None:
    """Return the version number if `name` is a member of the artifact family.

    Permissive per I1a: draft.md, draft2.md, draft-v2.md, draft-v1.md all parse.
    A bare name is version 1.
    """
    m = re.fullmatch(rf"{re.escape(family)}[-_]?v?(\d*)\.md", name)
    if not m:
        return None
    return int(m.group(1)) if m.group(1) else 1


def read_packet(root: Path, workflow: dict) -> PacketSnapshot:
    root = Path(root)
    snap = PacketSnapshot(root=root)
    if not root.is_dir():
        return snap

    snap.files = sorted(p.name for p in root.iterdir() if p.is_file())

    family = workflow.get("artifact", {}).get("family", "draft")
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

        round_match = re.fullmatch(r"decisions-(\d+)\.md", name)
        if round_match:
            n = int(round_match.group(1))
            snap.rounds[n] = RoundInfo(
                number=n, sections=_parse_sections((root / name).read_text())
            )
            continue

        if name == "adoption.md":
            snap.adoption = AdoptionInfo(
                sections=_parse_sections((root / name).read_text())
            )

    canonical = workflow.get("artifact", {}).get("canonical")
    if snap.artifact is not None and canonical:
        snap.artifact_canonical = snap.artifact == canonical

    runs_path = root / "runs.jsonl"
    if runs_path.exists():
        for line in runs_path.read_text().splitlines():
            line = line.strip()
            if line:
                snap.runs.append(json.loads(line))

    return snap
