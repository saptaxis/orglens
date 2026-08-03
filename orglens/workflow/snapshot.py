"""A packet's shape: a root, the names inside it, and its run log.

The engine does not know what a document is. It does not parse a role card,
follow a name pattern, or track versions or a most-current member of a
family. All it can say about a packet is what filesystem stat already
tells it — which names sit directly inside — plus what it has recorded
about itself in its own run log.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orglens.workflow.runstate import read_entries


@dataclass
class PacketSnapshot:
    root: Path
    files: list[str]
    runs: list[dict]


def read_packet(root: Path) -> PacketSnapshot:
    """Read a packet's shape: its filenames and its run log.

    A root that does not exist, or that is not a directory, yields an
    empty snapshot rather than an exception.
    """
    if not root.is_dir():
        return PacketSnapshot(root=root, files=[], runs=[])

    files = sorted(entry.name for entry in root.iterdir() if entry.is_file())
    return PacketSnapshot(root=root, files=files, runs=read_entries(root))
