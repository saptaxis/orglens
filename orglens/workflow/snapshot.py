"""A read-only picture of a packet directory.

A packet is a directory on disk. The snapshot never invents a filename: the
brief is found by the glob the deck declares in ``workflow["brief"]``, and
the artifact is found by the family it declares in ``workflow["artifact"]``.
The only filename this module names itself is ``runs.jsonl``, and it does
not even open that file directly — ``read_entries`` does.

Artifacts are one canonical file with git as their history: each write lands
on the same name, and the history lives in the commits. A file the deck did
not declare is just a name in ``files``; the engine never opens it.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from orglens.workflow.runstate import read_entries

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---", re.DOTALL)


@dataclass
class PacketSnapshot:
    root: Path
    files: list[str] = field(default_factory=list)
    brief: str | None = None
    brief_frontmatter: dict = field(default_factory=dict)
    artifact: str | None = None
    artifact_canonical: bool = False
    runs: list[dict] = field(default_factory=list)


def _parse_frontmatter(text: str) -> dict:
    """Parse the leading ``---`` block. Absent or malformed yields ``{}``."""
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _family_version(name: str, family: str) -> int | None:
    """Return ``name``'s version within ``family``, or ``None`` if it is not
    a member. A bare family name (``draft.md``) is version 1; ``draft2.md``
    and ``draft-v2.md`` are both version 2.
    """
    match = re.fullmatch(rf"{re.escape(family)}(?:-?v?(\d+))?\.md", name)
    if match is None:
        return None
    digits = match.group(1)
    return int(digits) if digits else 1


def read_packet(root: Path, workflow: dict) -> PacketSnapshot:
    """Read the filenames present in ``root`` and classify them by the
    roles ``workflow`` declares. A missing or non-directory ``root`` yields
    an empty snapshot rather than an error. A file fills at most one role:
    the brief is checked first, then the artifact family.
    """
    if not root.is_dir():
        return PacketSnapshot(root=root)

    files = sorted(p.name for p in root.iterdir() if p.is_file())

    brief_glob = workflow.get("brief")
    brief = None
    if brief_glob:
        for name in files:
            if fnmatch.fnmatch(name, brief_glob):
                brief = name
                break

    brief_frontmatter: dict = {}
    if brief is not None:
        brief_frontmatter = _parse_frontmatter((root / brief).read_text())

    artifact_config = workflow.get("artifact") or {}
    family = artifact_config.get("family")

    artifact = None
    best_version: int | None = None
    if family:
        for name in files:
            if name == brief:
                continue
            version = _family_version(name, family)
            if version is None:
                continue
            if best_version is None or version > best_version:
                best_version = version
                artifact = name

    artifact_canonical = artifact is not None and artifact == artifact_config.get(
        "canonical"
    )

    runs = read_entries(root)

    return PacketSnapshot(
        root=root,
        files=files,
        brief=brief,
        brief_frontmatter=brief_frontmatter,
        artifact=artifact,
        artifact_canonical=artifact_canonical,
        runs=runs,
    )
